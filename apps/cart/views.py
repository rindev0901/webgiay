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
from .models import Order
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator

Product = apps.get_model('products', 'Product')


def _get_cart(request):
    return request.session.setdefault('cart', {})


def cart_detail(request):
    items = []
    total = Decimal('0')

    if request.user.is_authenticated:
        for item in get_user_cart_items(request.user):
            price = item.price or item.product.final_price
            subtotal = price * item.quantity
            items.append({
                'product': item.product,
                'quantity': item.quantity,
                'price': price,
                'subtotal': subtotal,
                'cart_item': item,
            })
            total += subtotal
    else:
        cart = get_session_cart(request.session)
        product_ids = [int(pid) for pid in cart.keys()] if cart else []
        products = Product.objects.filter(id__in=product_ids)
        for p in products:
            pid = str(p.pk)
            qty = int(cart.get(pid, {}).get('quantity', 0))
            price = getattr(p, 'discount_price', None) or getattr(p, 'price', 0)
            subtotal = price * qty
            items.append({
                'product': p,
                'quantity': qty,
                'price': price,
                'subtotal': subtotal,
            })
            total += subtotal

    return render(request, 'cart_detail.html', {'cart_items': items, 'total': total})


@require_POST
def add_to_cart(request, product_id):
    qty = int(request.POST.get('quantity', 1))
    product = get_object_or_404(Product, pk=product_id)

    if request.user.is_authenticated:
        add_product_to_user_cart(request.user, product, qty)
    else:
        cart = _get_cart(request)
        pid = str(product_id)
        cart.setdefault(pid, {'quantity': 0})
        cart[pid]['quantity'] = cart[pid].get('quantity', 0) + qty
        request.session.modified = True

    next_url = request.POST.get(
        'next') or request.META.get('HTTP_REFERER') or '/'
    return redirect(next_url)


@require_POST
def update_cart(request, product_id):
    qty = int(request.POST.get('quantity', 0))
    product = get_object_or_404(Product, pk=product_id)

    if request.user.is_authenticated:
        set_user_cart_item_quantity(request.user, product, qty)
    else:
        cart = _get_cart(request)
        pid = str(product_id)
        if qty > 0:
            cart[pid] = {'quantity': qty}
        else:
            cart.pop(pid, None)
        request.session.modified = True

    return redirect('cart:cart_detail')


def remove_from_cart(request, product_id):
    product = get_object_or_404(Product, pk=product_id)

    if request.user.is_authenticated:
        remove_product_from_user_cart(request.user, product)
    else:
        cart = _get_cart(request)
        cart.pop(str(product_id), None)
        request.session.modified = True

    return redirect('cart:cart_detail')


def clear_cart(request):
    if request.user.is_authenticated:
        clear_user_cart(request.user)
    clear_session_cart(request.session)
    return redirect('cart:cart_detail')


@require_POST
def momo_checkout(request):
    order = create_order_from_cart(request.user if request.user.is_authenticated else None, request.session)
    if not order:
        messages.error(request, 'Giỏ hàng trống, không thể thanh toán.')
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
        return redirect('cart:cart_detail')

    return redirect(pay_url)


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
