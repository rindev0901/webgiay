from decimal import Decimal
from django.contrib import messages
from django.conf import settings
from django.http import JsonResponse, HttpResponseBadRequest
from django.urls import reverse
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt

from django.shortcuts import render, redirect, get_object_or_404
from django.apps import apps
from django.views.decorators.http import require_POST

from .momo import create_momo_payment, get_payment_result_code, verify_momo_signature
from .services import (
    add_product_to_user_cart,
    clear_session_cart,
    clear_user_cart,
    create_order_from_cart,
    get_session_cart,
    get_user_cart_items,
    remove_product_from_user_cart,
    set_user_cart_item_quantity,
)
from apps.products.inventory import check_stock, deduct_stock, restore_stock
from .forms import CheckoutForm
from .models import Order, Voucher
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator

Product = apps.get_model('products', 'Product')


def _get_cart(request):
    return request.session.setdefault('cart', {})


def cart_detail(request):
    items = []
    total = Decimal('0')

    from apps.products.models import ProductVariant

    if request.user.is_authenticated:
        for item in get_user_cart_items(request.user):
            price = item.price or item.product.final_price
            subtotal = price * item.quantity
            # Stock chính xác theo variant, fallback tổng nếu không có
            if item.variant:
                stock = item.variant.stock
            else:
                stock = sum(
                    v.stock for v in ProductVariant.objects.filter(
                        product=item.product, is_active=True
                    )
                )
            items.append({
                'product': item.product,
                'variant': item.variant,
                'quantity': item.quantity,
                'price': price,
                'subtotal': subtotal,
                'cart_item': item,
                'stock': stock,
            })
            total += subtotal
    else:
        cart = get_session_cart(request.session)
        for key, payload in cart.items():
            product_id = payload.get('product_id') or key
            variant_id = payload.get('variant_id')
            try:
                p = Product.objects.get(pk=int(product_id))
            except (Product.DoesNotExist, ValueError):
                continue
            qty = int(payload.get('quantity', 0))
            variant = None
            if variant_id:
                variant = ProductVariant.objects.filter(pk=variant_id, product=p, is_active=True).first()
            price = (variant.price if variant and variant.price else None) or getattr(p, 'discount_price', None) or p.price
            subtotal = price * qty
            stock = variant.stock if variant else sum(
                v.stock for v in ProductVariant.objects.filter(product=p, is_active=True)
            )
            items.append({
                'product': p,
                'variant': variant,
                'quantity': qty,
                'price': price,
                'subtotal': subtotal,
                'stock': stock,
            })
            total += subtotal

    # Sản phẩm đã xem gần đây (lưu trong session)
    rv_ids = request.session.get('recently_viewed', [])
    recently_viewed = []
    if rv_ids:
        rv_qs = Product.objects.filter(id__in=rv_ids, is_active=True).prefetch_related('images')
        rv_map = {p.id: p for p in rv_qs}
        recently_viewed = [rv_map[pid] for pid in rv_ids if pid in rv_map]

    return render(request, 'cart_detail.html', {
        'cart_items': items,
        'total': total,
        'recently_viewed': recently_viewed,
    })


@login_required
def checkout(request):
    items = []
    total = Decimal('0')

    from apps.products.models import ProductVariant

    if request.user.is_authenticated:
        for item in get_user_cart_items(request.user):
            price = item.price or item.product.final_price
            subtotal = price * item.quantity
            items.append({
                'product': item.product,
                'variant': item.variant,
                'quantity': item.quantity,
                'price': price,
                'subtotal': subtotal,
                'cart_item': item,
            })
            total += subtotal
    else:
        cart = get_session_cart(request.session)
        for key, payload in cart.items():
            product_id = payload.get('product_id') or key
            variant_id = payload.get('variant_id')
            try:
                p = Product.objects.get(pk=int(product_id))
            except (Product.DoesNotExist, ValueError):
                continue
            qty = int(payload.get('quantity', 0))
            variant = None
            if variant_id:
                variant = ProductVariant.objects.filter(pk=variant_id, product=p, is_active=True).first()
            price = (variant.price if variant and variant.price else None) or getattr(p, 'discount_price', None) or p.price
            subtotal = price * qty
            items.append({
                'product': p,
                'variant': variant,
                'quantity': qty,
                'price': price,
                'subtotal': subtotal,
            })
            total += subtotal

    if not items:
        messages.error(request, 'Giỏ hàng trống, chưa thể thanh toán.')
        return redirect('cart:cart_detail')

    # Kiểm tra tồn kho trước khi cho phép checkout
    stock_errors = check_stock(items)
    if stock_errors:
        for err in stock_errors:
            messages.error(
                request,
                f'"{err["product"]}" chỉ còn {err["available"]} sản phẩm, bạn đặt {err["requested"]}.'
            )
        return redirect('cart:cart_detail')

    # Đọc voucher từ session
    voucher_code = request.session.get('voucher_code', '')
    voucher = None
    discount_amount = Decimal('0')
    if voucher_code:
        v = Voucher.objects.filter(code=voucher_code.upper(), is_active=True).first()
        if v:
            ok, _ = v.is_valid(total)
            if ok:
                voucher = v
                discount_amount = v.calc_discount(total)

    final_total = total - discount_amount

    initial = {}
    if request.user.is_authenticated:
        initial['email'] = getattr(request.user, 'email', '') or ''
        if getattr(request.user, 'first_name', '') or getattr(request.user, 'last_name', ''):
            initial['full_name'] = f"{request.user.first_name} {request.user.last_name}".strip()

    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            order = create_order_from_cart(
                request.user if request.user.is_authenticated else None,
                request.session,
                form.cleaned_data,
                voucher=voucher,
            )
            if not order:
                messages.error(request, 'Không thể tạo đơn hàng từ giỏ hàng hiện tại.')
                return redirect('cart:cart_detail')

            # Xóa voucher khỏi session sau khi tạo đơn
            request.session.pop('voucher_code', None)

            redirect_url = request.build_absolute_uri(reverse('cart:momo_return'))
            ipn_url = request.build_absolute_uri(reverse('cart:momo_ipn'))

            try:
                request_payload, response_payload = create_momo_payment(order, redirect_url, ipn_url)
            except RuntimeError as exc:
                order.status = order.Status.FAILED
                order.momo_message = str(exc)
                order.save(update_fields=['status', 'momo_message', 'updated_at'])
                messages.error(request, str(exc))
                return redirect('cart:order_detail', code=order.code)

            order.momo_request_id = request_payload['requestId']
            order.momo_order_id = request_payload['orderId']
            order.momo_pay_url = response_payload.get('payUrl', '')
            order.momo_result_code = response_payload.get('resultCode')
            order.momo_message = response_payload.get('message', '')
            order.momo_response_payload = str(response_payload)
            order.save(update_fields=[
                'momo_request_id',
                'momo_order_id',
                'momo_pay_url',
                'momo_result_code',
                'momo_message',
                'momo_response_payload',
                'updated_at',
            ])

            pay_url = response_payload.get('payUrl')
            if not pay_url:
                messages.error(request, 'MoMo chưa trả về đường dẫn thanh toán.')
                return redirect('cart:order_detail', code=order.code)

            return redirect(pay_url)
    else:
        form = CheckoutForm(initial=initial)

    return render(request, 'checkout.html', {
        'form': form,
        'cart_items': items,
        'total': total,
        'voucher': voucher,
        'discount_amount': discount_amount,
        'final_total': final_total,
        'voucher_code': voucher_code,
    })


@require_POST
def add_to_cart(request, product_id):
    qty = int(request.POST.get('quantity', 1))
    product = get_object_or_404(Product, pk=product_id)

    from apps.products.models import ProductVariant
    variant_id = request.POST.get('variant_id')
    variant = None
    if variant_id:
        variant = ProductVariant.objects.filter(pk=variant_id, product=product, is_active=True).first()

    # Validate stock
    if variant:
        stock = variant.stock
    else:
        stock = sum(v.stock for v in ProductVariant.objects.filter(product=product, is_active=True))

    if request.user.is_authenticated:
        # Lấy qty đang có trong giỏ cho đúng variant
        current_qty = 0
        try:
            from .models import Cart, CartItem
            cart_obj = Cart.objects.get(user=request.user)
            cart_item = CartItem.objects.get(cart=cart_obj, product=product, variant=variant)
            current_qty = cart_item.quantity
        except Exception:
            pass

        if current_qty + qty > stock:
            messages.error(
                request,
                f'"{product.name}" chỉ còn {stock} sản phẩm '
                f'(bạn đã có {current_qty} trong giỏ).'
            )
            next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or '/'
            return redirect(next_url)

        add_product_to_user_cart(request.user, product, qty, variant=variant)
    else:
        cart = _get_cart(request)
        # Session cart key theo variant để tách riêng từng size
        key = f'{product_id}_{variant_id}' if variant_id else str(product_id)
        current_qty = int(cart.get(key, {}).get('quantity', 0))

        if current_qty + qty > stock:
            messages.error(
                request,
                f'"{product.name}" chỉ còn {stock} sản phẩm '
                f'(bạn đã có {current_qty} trong giỏ).'
            )
            next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or '/'
            return redirect(next_url)

        cart.setdefault(key, {'quantity': 0, 'product_id': product_id, 'variant_id': variant_id})
        cart[key]['quantity'] = current_qty + qty
        request.session.modified = True

    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or '/'
    return redirect(next_url)


@require_POST
def update_cart(request, product_id):
    qty = int(request.POST.get('quantity', 0))
    product = get_object_or_404(Product, pk=product_id)

    from apps.products.models import ProductVariant
    variant_id = request.POST.get('variant_id')
    variant = None
    if variant_id:
        variant = ProductVariant.objects.filter(pk=variant_id, product=product, is_active=True).first()

    if qty > 0 and variant:
        if qty > variant.stock:
            messages.error(
                request,
                f'"{product.name}" size {variant.size.name} chỉ còn {variant.stock} sản phẩm. Đã điều chỉnh.'
            )
            qty = variant.stock

    if request.user.is_authenticated:
        set_user_cart_item_quantity(request.user, product, qty, variant=variant)
    else:
        cart = _get_cart(request)
        key = f'{product_id}_{variant_id}' if variant_id else str(product_id)
        if qty > 0:
            cart[key] = {'quantity': qty, 'product_id': product_id, 'variant_id': variant_id}
        else:
            cart.pop(key, None)
        request.session.modified = True

    return redirect('cart:cart_detail')


def remove_from_cart(request, product_id):
    product = get_object_or_404(Product, pk=product_id)

    from apps.products.models import ProductVariant
    variant_id = request.POST.get('variant_id') or request.GET.get('variant_id')
    variant = None
    if variant_id:
        variant = ProductVariant.objects.filter(pk=variant_id, product=product).first()

    if request.user.is_authenticated:
        remove_product_from_user_cart(request.user, product, variant=variant)
    else:
        cart = _get_cart(request)
        key = f'{product_id}_{variant_id}' if variant_id else str(product_id)
        cart.pop(key, None)
        # fallback xóa cả key cũ dạng str(product_id)
        cart.pop(str(product_id), None)
        request.session.modified = True

    return redirect('cart:cart_detail')


def clear_cart(request):
    if request.user.is_authenticated:
        clear_user_cart(request.user)
    clear_session_cart(request.session)
    return redirect('cart:cart_detail')


@require_POST
def apply_voucher(request):
    """AJAX: kiểm tra và lưu voucher vào session."""
    from django.utils import timezone
    code = request.POST.get('code', '').strip().upper()

    if not code:
        return JsonResponse({'ok': False, 'error': 'Vui lòng nhập mã voucher.'})

    # Tính tổng giỏ hàng hiện tại
    total = Decimal('0')
    if request.user.is_authenticated:
        for item in get_user_cart_items(request.user):
            total += (item.price or item.product.final_price) * item.quantity
    else:
        cart = get_session_cart(request.session)
        for pid, payload in cart.items():
            from django.apps import apps as _apps
            Product_ = _apps.get_model('products', 'Product')
            p = Product_.objects.filter(pk=pid).first()
            if p:
                total += (p.final_price) * int(payload.get('quantity', 0))

    # Tra cứu voucher
    voucher = Voucher.objects.filter(code=code).first()
    if not voucher:
        return JsonResponse({'ok': False, 'error': 'Mã voucher không tồn tại.'})

    ok, err = voucher.is_valid(total)
    if not ok:
        return JsonResponse({'ok': False, 'error': err})

    discount = int(voucher.calc_discount(total))

    # Lưu vào session
    request.session['voucher_code'] = code
    request.session.modified = True

    return JsonResponse({
        'ok': True,
        'code': code,
        'description': voucher.description or f'Giảm {discount:,}₫',
        'discount_amount': discount,
        'final_total': int(total) - discount,
    })


@require_POST
def remove_voucher(request):
    """Xóa voucher khỏi session."""
    request.session.pop('voucher_code', None)
    return JsonResponse({'ok': True})


@require_POST
def momo_checkout(request):
    return redirect('cart:checkout')


def _momo_payload(request):
    data = request.POST.dict() if request.method == 'POST' else request.GET.dict()
    return data


def momo_return(request):
    payload = _momo_payload(request)
    order_id = payload.get('orderId')
    order = None
    if order_id:
        order = get_object_or_404(Order, code=order_id)

    if not order:
        messages.error(request, 'Không tìm thấy đơn hàng MoMo.')
        return redirect('cart:cart_detail')

    if verify_momo_signature(payload) and get_payment_result_code(payload) == 0:
        order.status = order.Status.PAID
        order.momo_trans_id = payload.get('transId', '')
        order.momo_result_code = get_payment_result_code(payload)
        order.momo_message = payload.get('message', '')
        order.save(update_fields=['status', 'momo_trans_id', 'momo_result_code', 'momo_message', 'updated_at'])
        # Trừ tồn kho
        deduct_stock(order, actor='momo_return')
        clear_session_cart(request.session)
        if request.user.is_authenticated:
            clear_user_cart(request.user)
        messages.success(request, f'Đơn hàng {order.code} đã thanh toán thành công bằng MoMo.')
    else:
        order.status = order.Status.FAILED
        order.momo_result_code = get_payment_result_code(payload)
        order.momo_message = payload.get('message', 'Thanh toán MoMo thất bại')
        order.save(update_fields=['status', 'momo_result_code', 'momo_message', 'updated_at'])
        messages.error(request, f'Thanh toán MoMo thất bại cho đơn hàng {order.code}.')

    return redirect('cart:cart_detail')


@csrf_exempt
def momo_ipn(request):
    payload = _momo_payload(request)
    order_id = payload.get('orderId')

    if not order_id:
        return JsonResponse({'resultCode': 99, 'message': 'Missing orderId'}, status=400)

    order = Order.objects.filter(code=order_id).first()
    if not order:
        return JsonResponse({'resultCode': 1, 'message': 'Order not found'})

    if verify_momo_signature(payload) and get_payment_result_code(payload) == 0:
        order.status = order.Status.PAID
        order.momo_trans_id = payload.get('transId', '')
        order.momo_result_code = get_payment_result_code(payload)
        order.momo_message = payload.get('message', '')
        order.save(update_fields=['status', 'momo_trans_id', 'momo_result_code', 'momo_message', 'updated_at'])
        deduct_stock(order, actor='momo_ipn')
        clear_session_cart(request.session)
        if request.user.is_authenticated:
            clear_user_cart(request.user)
        return JsonResponse({'resultCode': 0, 'message': 'Success'})

    order.status = order.Status.FAILED
    order.momo_result_code = get_payment_result_code(payload)
    order.momo_message = payload.get('message', 'Thanh toán MoMo thất bại')
    order.save(update_fields=['status', 'momo_result_code', 'momo_message', 'updated_at'])
    return JsonResponse({'resultCode': 1, 'message': 'Invalid signature or payment failed'})


@login_required
def orders_list(request):
    qs = Order.objects.filter(user=request.user).order_by('-created_at')
    paginator = Paginator(qs, 12)
    page = request.GET.get('page')
    page_obj = paginator.get_page(page)
    return render(request, 'orders/order_list.html', {'page_obj': page_obj, 'paginator': paginator})


def order_detail(request, code):
    order = get_object_or_404(Order, code=code)
    if order.user and request.user != order.user and not request.user.is_staff:
        return HttpResponseBadRequest('Bạn không có quyền xem đơn hàng này.')
    return render(request, 'orders/order_detail.html', {'order': order})


@require_POST
def order_retry(request, code):
    order = get_object_or_404(Order, code=code)
    if order.status not in (order.Status.PENDING, order.Status.FAILED):
        messages.error(request, 'Đơn hàng không ở trạng thái có thể thanh toán lại.')
        return redirect('cart:cart_detail')

    redirect_url = request.build_absolute_uri(reverse('cart:momo_return'))
    ipn_url = request.build_absolute_uri(reverse('cart:momo_ipn'))

    try:
        request_payload, response_payload = create_momo_payment(order, redirect_url, ipn_url)
    except RuntimeError as exc:
        order.status = order.Status.FAILED
        order.momo_message = str(exc)
        order.save(update_fields=['status', 'momo_message', 'updated_at'])
        messages.error(request, str(exc))
        return redirect('cart:cart_detail')

    order.momo_request_id = request_payload['requestId']
    order.momo_order_id = request_payload['orderId']
    order.momo_pay_url = response_payload.get('payUrl', '')
    order.momo_result_code = response_payload.get('resultCode')
    order.momo_message = response_payload.get('message', '')
    order.momo_response_payload = str(response_payload)
    order.save(update_fields=[
        'momo_request_id', 'momo_order_id', 'momo_pay_url', 'momo_result_code', 'momo_message', 'momo_response_payload', 'updated_at'
    ])

    pay_url = response_payload.get('payUrl')
    if not pay_url:
        messages.error(request, 'MoMo chưa trả về đường dẫn thanh toán.')
        return redirect('cart:cart_detail')

    return redirect(pay_url)
