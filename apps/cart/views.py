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
from .sepay import build_sepay_form_data, parse_sepay_ipn, verify_sepay_ipn
from .email_service import send_order_confirmation
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
from apps.products.inventory import check_stock, restore_stock
from .forms import CheckoutForm
from .models import Order, Voucher
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator

Product = apps.get_model("products", "Product")


def _get_cart(request):
    return request.session.setdefault("cart", {})


def cart_detail(request):
    items = []
    total = Decimal("0")

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
                    v.stock
                    for v in ProductVariant.objects.filter(
                        product=item.product, is_active=True
                    )
                )
            items.append(
                {
                    "product": item.product,
                    "variant": item.variant,
                    "quantity": item.quantity,
                    "price": price,
                    "subtotal": subtotal,
                    "cart_item": item,
                    "stock": stock,
                }
            )
            total += subtotal
    else:
        cart = get_session_cart(request.session)
        for key, payload in cart.items():
            product_id = payload.get("product_id") or key
            variant_id = payload.get("variant_id")
            try:
                p = Product.objects.get(pk=int(product_id))
            except (Product.DoesNotExist, ValueError):
                continue
            qty = int(payload.get("quantity", 0))
            variant = None
            if variant_id:
                variant = ProductVariant.objects.filter(
                    pk=variant_id, product=p, is_active=True
                ).first()
            price = (
                (variant.price if variant and variant.price else None)
                or getattr(p, "discount_price", None)
                or p.price
            )
            subtotal = price * qty
            stock = (
                variant.stock
                if variant
                else sum(
                    v.stock
                    for v in ProductVariant.objects.filter(product=p, is_active=True)
                )
            )
            items.append(
                {
                    "product": p,
                    "variant": variant,
                    "quantity": qty,
                    "price": price,
                    "subtotal": subtotal,
                    "stock": stock,
                }
            )
            total += subtotal

    # Sản phẩm đã xem gần đây (lưu trong session)
    rv_ids = request.session.get("recently_viewed", [])
    recently_viewed = []
    if rv_ids:
        rv_qs = Product.objects.filter(id__in=rv_ids, is_active=True).prefetch_related(
            "images"
        )
        rv_map = {p.id: p for p in rv_qs}
        recently_viewed = [rv_map[pid] for pid in rv_ids if pid in rv_map]

    return render(
        request,
        "cart_detail.html",
        {
            "cart_items": items,
            "total": total,
            "recently_viewed": recently_viewed,
        },
    )


@login_required
def checkout(request):
    items = []
    total = Decimal("0")

    from apps.products.models import ProductVariant

    if request.user.is_authenticated:
        for item in get_user_cart_items(request.user):
            price = item.price or item.product.final_price
            subtotal = price * item.quantity
            items.append(
                {
                    "product": item.product,
                    "variant": item.variant,
                    "quantity": item.quantity,
                    "price": price,
                    "subtotal": subtotal,
                    "cart_item": item,
                }
            )
            total += subtotal
    else:
        cart = get_session_cart(request.session)
        for key, payload in cart.items():
            product_id = payload.get("product_id") or key
            variant_id = payload.get("variant_id")
            try:
                p = Product.objects.get(pk=int(product_id))
            except (Product.DoesNotExist, ValueError):
                continue
            qty = int(payload.get("quantity", 0))
            variant = None
            if variant_id:
                variant = ProductVariant.objects.filter(
                    pk=variant_id, product=p, is_active=True
                ).first()
            price = (
                (variant.price if variant and variant.price else None)
                or getattr(p, "discount_price", None)
                or p.price
            )
            subtotal = price * qty
            items.append(
                {
                    "product": p,
                    "variant": variant,
                    "quantity": qty,
                    "price": price,
                    "subtotal": subtotal,
                }
            )
            total += subtotal

    if not items:
        messages.error(request, "Giỏ hàng trống, chưa thể thanh toán.")
        return redirect("cart:cart_detail")

    # Kiểm tra tồn kho trước khi cho phép checkout
    stock_errors = check_stock(items)
    if stock_errors:
        for err in stock_errors:
            messages.error(
                request,
                f'"{err["product"]}" chỉ còn {err["available"]} sản phẩm, bạn đặt {err["requested"]}.',
            )
        return redirect("cart:cart_detail")

    # Đọc voucher từ session
    voucher_code = request.session.get("voucher_code", "")
    voucher = None
    discount_amount = Decimal("0")
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
        initial["email"] = getattr(request.user, "email", "") or ""
        if getattr(request.user, "first_name", "") or getattr(
            request.user, "last_name", ""
        ):
            initial["full_name"] = (
                f"{request.user.first_name} {request.user.last_name}".strip()
            )

    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            order = create_order_from_cart(
                request.user if request.user.is_authenticated else None,
                request.session,
                form.cleaned_data,
                voucher=voucher,
            )
            if not order:
                messages.error(request, "Không thể tạo đơn hàng từ giỏ hàng hiện tại.")
                return redirect("cart:cart_detail")

            # Xóa voucher khỏi session sau khi tạo đơn
            request.session.pop("voucher_code", None)

            redirect_url = request.build_absolute_uri(reverse("cart:momo_return"))
            ipn_url = request.build_absolute_uri(reverse("cart:momo_ipn"))

            try:
                request_payload, response_payload = create_momo_payment(
                    order, redirect_url, ipn_url
                )
            except RuntimeError as exc:
                order.status = order.Status.FAILED
                order.momo_message = str(exc)
                order.save(update_fields=["status", "momo_message", "updated_at"])
                messages.error(request, str(exc))
                return redirect("cart:order_detail", code=order.code)

            order.momo_request_id = request_payload["requestId"]
            order.momo_order_id = request_payload["orderId"]
            order.momo_pay_url = response_payload.get("payUrl", "")
            order.momo_result_code = response_payload.get("resultCode")
            order.momo_message = response_payload.get("message", "")
            order.momo_response_payload = str(response_payload)
            order.save(
                update_fields=[
                    "momo_request_id",
                    "momo_order_id",
                    "momo_pay_url",
                    "momo_result_code",
                    "momo_message",
                    "momo_response_payload",
                    "updated_at",
                ]
            )

            pay_url = response_payload.get("payUrl")
            if not pay_url:
                messages.error(request, "MoMo chưa trả về đường dẫn thanh toán.")
                return redirect("cart:order_detail", code=order.code)

            return redirect(pay_url)
    else:
        form = CheckoutForm(initial=initial)

    return render(
        request,
        "checkout.html",
        {
            "form": form,
            "cart_items": items,
            "total": total,
            "voucher": voucher,
            "discount_amount": discount_amount,
            "final_total": final_total,
            "voucher_code": voucher_code,
        },
    )


@require_POST
def add_to_cart(request, product_id):
    qty = int(request.POST.get("quantity", 1))
    product = get_object_or_404(Product, pk=product_id)

    from apps.products.models import ProductVariant

    variant_id = request.POST.get("variant_id")
    variant = None
    if variant_id:
        variant = ProductVariant.objects.filter(
            pk=variant_id, product=product, is_active=True
        ).first()

    # Validate stock
    if variant:
        stock = variant.stock
    else:
        stock = sum(
            v.stock
            for v in ProductVariant.objects.filter(product=product, is_active=True)
        )

    if request.user.is_authenticated:
        # Lấy qty đang có trong giỏ cho đúng variant
        current_qty = 0
        try:
            from .models import Cart, CartItem

            cart_obj = Cart.objects.get(user=request.user)
            cart_item = CartItem.objects.get(
                cart=cart_obj, product=product, variant=variant
            )
            current_qty = cart_item.quantity
        except Exception:
            pass

        if current_qty + qty > stock:
            messages.error(
                request,
                f'"{product.name}" chỉ còn {stock} sản phẩm '
                f"(bạn đã có {current_qty} trong giỏ).",
            )
            next_url = (
                request.POST.get("next") or request.META.get("HTTP_REFERER") or "/"
            )
            return redirect(next_url)

        add_product_to_user_cart(request.user, product, qty, variant=variant)
    else:
        cart = _get_cart(request)
        # Session cart key theo variant để tách riêng từng size
        key = f"{product_id}_{variant_id}" if variant_id else str(product_id)
        current_qty = int(cart.get(key, {}).get("quantity", 0))

        if current_qty + qty > stock:
            messages.error(
                request,
                f'"{product.name}" chỉ còn {stock} sản phẩm '
                f"(bạn đã có {current_qty} trong giỏ).",
            )
            next_url = (
                request.POST.get("next") or request.META.get("HTTP_REFERER") or "/"
            )
            return redirect(next_url)

        cart.setdefault(
            key, {"quantity": 0, "product_id": product_id, "variant_id": variant_id}
        )
        cart[key]["quantity"] = current_qty + qty
        request.session.modified = True

    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or "/"
    return redirect(next_url)


@require_POST
def update_cart(request, product_id):
    qty = int(request.POST.get("quantity", 0))
    product = get_object_or_404(Product, pk=product_id)

    from apps.products.models import ProductVariant

    variant_id = request.POST.get("variant_id")
    variant = None
    if variant_id:
        variant = ProductVariant.objects.filter(
            pk=variant_id, product=product, is_active=True
        ).first()

    if qty > 0 and variant:
        if qty > variant.stock:
            messages.error(
                request,
                f'"{product.name}" size {variant.size.name} chỉ còn {variant.stock} sản phẩm. Đã điều chỉnh.',
            )
            qty = variant.stock

    if request.user.is_authenticated:
        set_user_cart_item_quantity(request.user, product, qty, variant=variant)
    else:
        cart = _get_cart(request)
        key = f"{product_id}_{variant_id}" if variant_id else str(product_id)
        if qty > 0:
            cart[key] = {
                "quantity": qty,
                "product_id": product_id,
                "variant_id": variant_id,
            }
        else:
            cart.pop(key, None)
        request.session.modified = True

    return redirect("cart:cart_detail")


def remove_from_cart(request, product_id):
    product = get_object_or_404(Product, pk=product_id)

    from apps.products.models import ProductVariant

    variant_id = request.POST.get("variant_id") or request.GET.get("variant_id")
    variant = None
    if variant_id:
        variant = ProductVariant.objects.filter(pk=variant_id, product=product).first()

    if request.user.is_authenticated:
        remove_product_from_user_cart(request.user, product, variant=variant)
    else:
        cart = _get_cart(request)
        key = f"{product_id}_{variant_id}" if variant_id else str(product_id)
        cart.pop(key, None)
        # fallback xóa cả key cũ dạng str(product_id)
        cart.pop(str(product_id), None)
        request.session.modified = True

    return redirect("cart:cart_detail")


def clear_cart(request):
    if request.user.is_authenticated:
        clear_user_cart(request.user)
    clear_session_cart(request.session)
    return redirect("cart:cart_detail")


@require_POST
def apply_voucher(request):
    """AJAX: kiểm tra và lưu voucher vào session."""
    from django.utils import timezone

    code = request.POST.get("code", "").strip().upper()

    if not code:
        return JsonResponse({"ok": False, "error": "Vui lòng nhập mã voucher."})

    # Tính tổng giỏ hàng hiện tại
    total = Decimal("0")
    if request.user.is_authenticated:
        for item in get_user_cart_items(request.user):
            total += (item.price or item.product.final_price) * item.quantity
    else:
        cart = get_session_cart(request.session)
        for pid, payload in cart.items():
            from django.apps import apps as _apps

            Product_ = _apps.get_model("products", "Product")
            p = Product_.objects.filter(pk=pid).first()
            if p:
                total += (p.final_price) * int(payload.get("quantity", 0))

    # Tra cứu voucher
    voucher = Voucher.objects.filter(code=code).first()
    if not voucher:
        return JsonResponse({"ok": False, "error": "Mã voucher không tồn tại."})

    ok, err = voucher.is_valid(total)
    if not ok:
        return JsonResponse({"ok": False, "error": err})

    discount = int(voucher.calc_discount(total))

    # Lưu vào session
    request.session["voucher_code"] = code
    request.session.modified = True

    return JsonResponse(
        {
            "ok": True,
            "code": code,
            "description": voucher.description or f"Giảm {discount:,}₫",
            "discount_amount": discount,
            "final_total": int(total) - discount,
        }
    )


@require_POST
def remove_voucher(request):
    """Xóa voucher khỏi session."""
    request.session.pop("voucher_code", None)
    return JsonResponse({"ok": True})


@require_POST
def momo_checkout(request):
    return redirect("cart:checkout")


def _momo_payload(request):
    data = request.POST.dict() if request.method == "POST" else request.GET.dict()
    return data


def momo_return(request):
    payload = _momo_payload(request)
    order_id = payload.get("orderId")
    order = None
    if order_id:
        order = get_object_or_404(Order, code=order_id)

    if not order:
        messages.error(request, "Không tìm thấy đơn hàng MoMo.")
        return redirect("cart:cart_detail")

    # Local dev: bỏ qua verify signature vì IPN không gọi được từ localhost
    from django.conf import settings as _settings

    payment_ok = _settings.DEBUG or (
        verify_momo_signature(payload) and get_payment_result_code(payload) == 0
    )

    if payment_ok:
        if order.payment_status != Order.PaymentStatus.PAID:

            order.status = Order.Status.PAID
            order.payment_status = Order.PaymentStatus.PAID
            order.order_status = Order.OrderStatus.PROCESSING
            order.momo_trans_id = payload.get("transId", "")
            order.momo_result_code = get_payment_result_code(payload)
            order.momo_message = payload.get("message", "")
            order.save(
                update_fields=[
                    "status",
                    "payment_status",
                    "order_status",
                    "momo_trans_id",
                    "momo_result_code",
                    "momo_message",
                    "updated_at",
                ]
            )

            order.log_status(
                Order.OrderStatus.PROCESSING,
                note="Thanh toán MoMo thành công — chờ admin duyệt đơn và trừ tồn kho",
                actor="momo_return",
            )
            send_order_confirmation(order, request)

        clear_session_cart(request.session)
        if request.user.is_authenticated:
            clear_user_cart(request.user)
        messages.success(
            request, f"Đơn hàng {order.code} đã thanh toán thành công bằng MoMo."
        )
    else:
        order.status = Order.Status.FAILED
        order.payment_status = Order.PaymentStatus.FAILED
        order.momo_result_code = get_payment_result_code(payload)
        order.momo_message = payload.get("message", "Thanh toán MoMo thất bại")
        order.save(
            update_fields=[
                "status",
                "payment_status",
                "momo_result_code",
                "momo_message",
                "updated_at",
            ]
        )
        messages.error(request, f"Thanh toán MoMo thất bại cho đơn hàng {order.code}.")

    return redirect("cart:order_detail", code=order.code)


@csrf_exempt
def momo_ipn(request):
    payload = _momo_payload(request)
    order_id = payload.get("orderId")

    if not order_id:
        return JsonResponse(
            {"resultCode": 99, "message": "Missing orderId"}, status=400
        )

    order = Order.objects.filter(code=order_id).first()
    if not order:
        return JsonResponse({"resultCode": 1, "message": "Order not found"})

    if verify_momo_signature(payload) and get_payment_result_code(payload) == 0:
        if order.payment_status != Order.PaymentStatus.PAID:

            order.status = Order.Status.PAID
            order.payment_status = Order.PaymentStatus.PAID
            order.order_status = Order.OrderStatus.PROCESSING
            order.momo_trans_id = payload.get("transId", "")
            order.momo_result_code = get_payment_result_code(payload)
            order.momo_message = payload.get("message", "")
            order.save(
                update_fields=[
                    "status",
                    "payment_status",
                    "order_status",
                    "momo_trans_id",
                    "momo_result_code",
                    "momo_message",
                    "updated_at",
                ]
            )

            order.log_status(
                Order.OrderStatus.PROCESSING,
                note="Thanh toán MoMo thành công — chờ admin duyệt đơn và trừ tồn kho",
                actor="momo_ipn",
            )
            send_order_confirmation(order)
        return JsonResponse({"resultCode": 0, "message": "Success"})

    order.status = order.Status.FAILED
    order.momo_result_code = get_payment_result_code(payload)
    order.momo_message = payload.get("message", "Thanh toán MoMo thất bại")
    order.save(
        update_fields=["status", "momo_result_code", "momo_message", "updated_at"]
    )
    return JsonResponse(
        {"resultCode": 1, "message": "Invalid signature or payment failed"}
    )


def _build_customer_tracking_steps(order):
    """
    Timeline hiển thị cho khách hàng chỉ gồm 3 trạng thái:
    1. Đang xử lý
    2. Đang giao hàng
    3. Đã giao hàng

    Nguyên tắc:
    - Không hiển thị trạng thái thanh toán ở đây.
    - Khi đơn đã lên trạng thái sau thì các trạng thái trước vẫn phải còn.
    - Nếu có log thì lấy thời gian/note từ log.
    - Nếu thiếu log cũ thì vẫn hiển thị mốc đó để không bị mất tiến trình.
    """
    statuses = [
        Order.OrderStatus.PROCESSING,
        Order.OrderStatus.SHIPPED,
        Order.OrderStatus.DELIVERED,
    ]

    labels = {
        Order.OrderStatus.PROCESSING: "Đang xử lý",
        Order.OrderStatus.SHIPPED: "Đang giao hàng",
        Order.OrderStatus.DELIVERED: "Đã giao hàng",
    }

    default_notes = {
        Order.OrderStatus.PROCESSING: "Đơn hàng đang được xử lý",
        Order.OrderStatus.SHIPPED: "Đơn hàng đang được giao",
        Order.OrderStatus.DELIVERED: "Đơn hàng đã được giao thành công",
    }

    logs = order.status_logs.filter(status__in=statuses).order_by("created_at")

    log_map = {}
    for log in logs:
        # Nếu một trạng thái có nhiều log thì lấy log đầu tiên để giữ mốc lịch sử ban đầu
        if log.status not in log_map:
            log_map[log.status] = log

    if order.order_status in statuses:
        current_index = statuses.index(order.order_status)
    else:
        current_index = 0

    steps = []

    for index, status in enumerate(statuses):
        log = log_map.get(status)

        if order.order_status == Order.OrderStatus.DELIVERED and index <= current_index:
            state = "done"
        elif index < current_index:
            state = "done"
        elif index == current_index:
            state = "active"
        else:
            state = "future"
            created_at = None
            note = ""

        if state != "future":
            if log:
                created_at = log.created_at
                note = log.note or default_notes.get(status, "")
            else:
                # Fallback cho các đơn cũ chưa có log đầy đủ
                if status == Order.OrderStatus.PROCESSING:
                    created_at = order.created_at
                    note = default_notes[status]
                elif status == Order.OrderStatus.DELIVERED and order.delivered_at:
                    created_at = order.delivered_at
                    note = default_notes[status]
                else:
                    note = default_notes.get(status, "")

        steps.append(
            {
                "status": status,
                "label": labels[status],
                "state": state,
                "created_at": created_at,
                "note": note,
            }
        )

    return steps
    """
    Timeline hiển thị cho khách hàng: chỉ 3 mốc nghiệp vụ.
    Không đưa payment_status như pending/paid vào lịch sử đơn hàng.
    """
    statuses = [
        Order.OrderStatus.PROCESSING,
        Order.OrderStatus.SHIPPED,
        Order.OrderStatus.DELIVERED,
    ]

    labels = {
        Order.OrderStatus.PROCESSING: "Đang xử lý",
        Order.OrderStatus.SHIPPED: "Đang giao hàng",
        Order.OrderStatus.DELIVERED: "Đã giao hàng",
    }

    log_map = {}
    for log in order.status_logs.filter(status__in=statuses).order_by("created_at"):
        log_map.setdefault(log.status, log)

    if order.order_status in statuses:
        current_index = statuses.index(order.order_status)
    else:
        current_index = 0

    steps = []

    for index, status in enumerate(statuses):
        if index < current_index:
            state = "done"
        elif index == current_index:
            state = "active"
        else:
            state = "future"

        log = log_map.get(status)
        created_at = None
        note = ""

        if state != "future":
            if log:
                created_at = log.created_at
                note = log.note
            elif status == Order.OrderStatus.PROCESSING:
                created_at = order.created_at
                note = "Đơn hàng đang được xử lý"
            elif status == Order.OrderStatus.DELIVERED and order.delivered_at:
                created_at = order.delivered_at

        steps.append(
            {
                "status": status,
                "label": labels[status],
                "state": state,
                "created_at": created_at,
                "note": note,
            }
        )

    return steps


def orders_list(request):
    qs = Order.objects.filter(user=request.user).order_by("-created_at")
    paginator = Paginator(qs, 12)
    page = request.GET.get("page")
    page_obj = paginator.get_page(page)
    return render(
        request,
        "orders/order_list.html",
        {"page_obj": page_obj, "paginator": paginator},
    )


def order_detail(request, code):
    order = get_object_or_404(Order, code=code)
    if order.user and request.user != order.user and not request.user.is_staff:
        return HttpResponseBadRequest("Bạn không có quyền xem đơn hàng này.")

    # Generate QR code as base64 for display in template
    qr_base64 = _generate_qr_base64(request, order)
    tracking_steps = _build_customer_tracking_steps(order)

    return render(
        request,
        "orders/order_detail.html",
        {
            "order": order,
            "qr_base64": qr_base64,
            "tracking_steps": tracking_steps,
        },
    )


def order_qr_confirm(request, code):
    """
    Trang xác nhận nhận hàng qua QR.
    - Chủ đơn hàng được xác nhận
    - Shipper/staff có quyền xem/sửa đơn hàng được xác nhận
    - Chỉ cho xác nhận khi đơn đang ở trạng thái Đang giao hàng
    """
    order = get_object_or_404(Order, code=code)
    already_confirmed = order.delivery_confirmed

    # Chỉ cho xác nhận QR khi admin đã chuyển sang Đang giao hàng
    valid_statuses = (Order.OrderStatus.SHIPPED,)

    is_owner = (
        request.user.is_authenticated and order.user and request.user == order.user
    )

    is_shipper = request.user.is_authenticated and (
        request.user.has_perm("cart.view_order")
        or request.user.has_perm("cart.change_order")
    )

    can_confirm = (
        (is_owner or is_shipper)
        and not already_confirmed
        and order.order_status in valid_statuses
    )

    if request.method == "POST":
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login

            return redirect_to_login(request.get_full_path())

        if not (is_owner or is_shipper):
            messages.error(request, "Bạn không có quyền xác nhận đơn hàng này.")
            return redirect("cart:order_qr_confirm", code=code)

        if already_confirmed:
            messages.warning(
                request, "Đơn hàng này đã được xác nhận nhận hàng trước đó."
            )
            return redirect("cart:order_qr_confirm", code=code)

        if order.order_status not in valid_statuses:
            messages.error(
                request,
                "Đơn hàng chưa ở trạng thái Đang giao hàng nên chưa thể xác nhận.",
            )
            return redirect("cart:order_qr_confirm", code=code)

        from django.utils import timezone

        order.order_status = Order.OrderStatus.DELIVERED
        order.payment_status = Order.PaymentStatus.PAID
        order.status = Order.Status.DELIVERED
        order.delivered_at = timezone.now()
        order.delivery_confirmed = True
        order.save(
            update_fields=[
                "order_status",
                "payment_status",
                "status",
                "delivered_at",
                "delivery_confirmed",
                "updated_at",
            ]
        )

        actor_label = (
            f"Shipper {request.user.username}"
            if is_shipper and not is_owner
            else f"Khách hàng {request.user.username}"
        )

        order.log_status(
            Order.OrderStatus.DELIVERED,
            note="Đã giao hàng thành công",
            actor=str(request.user),
        )
        messages.success(request, "Xác nhận nhận hàng thành công!")
        return redirect("cart:order_qr_confirm", code=code)

    tracking_steps = _build_customer_tracking_steps(order)

    return render(
        request,
        "orders/order_qr_confirm.html",
        {
            "order": order,
            "already_confirmed": already_confirmed,
            "can_confirm": can_confirm,
            "is_owner": is_owner,
            "is_shipper": is_shipper,
            "tracking_steps": tracking_steps,
        },
    )


def _generate_qr_base64(request, order):
    """Generate QR code PNG as base64 string."""
    try:
        import qrcode
        import io
        import base64

        confirm_url = request.build_absolute_uri(
            reverse("cart:order_qr_confirm", kwargs={"code": order.code})
        )
        qr = qrcode.QRCode(version=1, box_size=8, border=2)
        qr.add_data(confirm_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception:
        return None


@require_POST
def order_retry(request, code):
    order = get_object_or_404(Order, code=code)
    if order.status not in (order.Status.PENDING, order.Status.FAILED):
        messages.error(request, "Đơn hàng không ở trạng thái có thể thanh toán lại.")
        return redirect("cart:order_detail", code=order.code)

    # Route theo payment_method đã lưu
    if order.payment_method == Order.PaymentMethod.SEPAY:
        # SePay: tạo lại form data và render redirect page
        success_url = request.build_absolute_uri(
            reverse("cart:sepay_return") + f"?order_code={order.code}"
        )
        error_url = request.build_absolute_uri(
            reverse("cart:sepay_return") + f"?order_code={order.code}&status=error"
        )
        cancel_url = request.build_absolute_uri(
            reverse("cart:sepay_return") + f"?order_code={order.code}&status=cancel"
        )
        customer_id = str(order.user.id) if order.user else ""
        form_data = build_sepay_form_data(
            order,
            success_url=success_url,
            error_url=error_url,
            cancel_url=cancel_url,
            customer_id=customer_id,
        )
        return render(request, "sepay_redirect.html", {"form_data": form_data})

    # MoMo (mặc định)
    redirect_url = request.build_absolute_uri(reverse("cart:momo_return"))
    ipn_url = request.build_absolute_uri(reverse("cart:momo_ipn"))

    try:
        request_payload, response_payload = create_momo_payment(
            order, redirect_url, ipn_url
        )
    except RuntimeError as exc:
        order.status = order.Status.FAILED
        order.momo_message = str(exc)
        order.save(update_fields=["status", "momo_message", "updated_at"])
        messages.error(request, str(exc))
        return redirect("cart:order_detail", code=order.code)

    order.momo_request_id = request_payload["requestId"]
    order.momo_order_id = request_payload["orderId"]
    order.momo_pay_url = response_payload.get("payUrl", "")
    order.momo_result_code = response_payload.get("resultCode")
    order.momo_message = response_payload.get("message", "")
    order.momo_response_payload = str(response_payload)
    order.save(
        update_fields=[
            "momo_request_id",
            "momo_order_id",
            "momo_pay_url",
            "momo_result_code",
            "momo_message",
            "momo_response_payload",
            "updated_at",
        ]
    )

    pay_url = response_payload.get("payUrl")
    if not pay_url:
        messages.error(request, "MoMo chưa trả về đường dẫn thanh toán.")
        return redirect("cart:order_detail", code=order.code)

    return redirect(pay_url)


# ══════════════════════════════════════════
# COD VIEW
# ══════════════════════════════════════════


@require_POST
@login_required
def cod_checkout(request):
    """
    Tạo đơn COD (Cash On Delivery).
    - payment_method = COD
    - payment_status = PENDING  (chưa thu tiền)
    - order_status   = NEW      (chờ admin xử lý)
    - Xóa giỏ hàng và gửi email xác nhận ngay sau khi tạo đơn.
    """
    items = []
    total = Decimal("0")

    for item in get_user_cart_items(request.user):
        price = item.price or item.product.final_price
        subtotal = price * item.quantity
        items.append(
            {
                "product": item.product,
                "variant": item.variant,
                "quantity": item.quantity,
                "price": price,
                "subtotal": subtotal,
                "cart_item": item,
            }
        )
        total += subtotal

    if not items:
        messages.error(request, "Giỏ hàng trống, chưa thể đặt hàng.")
        return redirect("cart:cart_detail")

    # Kiểm tra tồn kho
    stock_errors = check_stock(items)
    if stock_errors:
        for err in stock_errors:
            messages.error(
                request,
                f'"{err["product"]}" chỉ còn {err["available"]} sản phẩm, bạn đặt {err["requested"]}.',
            )
        return redirect("cart:cart_detail")

    # Đọc voucher từ session
    voucher_code = request.session.get("voucher_code", "")
    voucher = None
    if voucher_code:
        v = Voucher.objects.filter(code=voucher_code.upper(), is_active=True).first()
        if v:
            ok, _ = v.is_valid(total)
            if ok:
                voucher = v

    form = CheckoutForm(request.POST)
    if not form.is_valid():
        messages.error(
            request, "Thông tin giao hàng không hợp lệ. Vui lòng kiểm tra lại."
        )
        return redirect("cart:cart_detail")

    order = create_order_from_cart(
        request.user,
        request.session,
        form.cleaned_data,
        voucher=voucher,
    )
    if not order:
        messages.error(request, "Không thể tạo đơn hàng. Vui lòng thử lại.")
        return redirect("cart:cart_detail")

    # Đánh dấu COD
    # Thanh toán: chờ thanh toán
    # Đơn hàng: đang xử lý
    order.payment_method = Order.PaymentMethod.COD
    order.payment_status = Order.PaymentStatus.PENDING
    order.order_status = Order.OrderStatus.PROCESSING

    # Đồng bộ field legacy để các màn hình cũ không bị lệch
    order.status = Order.Status.PROCESSING
    order.save(
        update_fields=[
            "payment_method",
            "payment_status",
            "order_status",
            "status",
            "updated_at",
        ]
    )

    order.log_status(
        Order.OrderStatus.PROCESSING,
        note="Đơn COD đang được xử lý",
        actor="customer",
    )

    # Xóa voucher và giỏ hàng
    request.session.pop("voucher_code", None)
    clear_session_cart(request.session)
    clear_user_cart(request.user)

    # Gửi email xác nhận trong background thread
    send_order_confirmation(order, request)

    messages.success(
        request,
        f"Đặt hàng thành công! Mã đơn hàng: {order.code}. "
        "Chúng tôi sẽ liên hệ xác nhận và giao hàng sớm nhất.",
    )
    return redirect("cart:order_detail", code=order.code)


# ══════════════════════════════════════════
# SEPAY VIEWS
# ══════════════════════════════════════════


@login_required
def sepay_checkout(request):
    """
    Tạo đơn hàng rồi render trang trung gian có HTML form tự submit tới SePay.
    """
    from apps.products.inventory import check_stock

    items = []
    total = Decimal("0")
    from apps.products.models import ProductVariant as _PV

    for item in get_user_cart_items(request.user):
        price = item.price or item.product.final_price
        subtotal = price * item.quantity
        items.append(
            {
                "product": item.product,
                "variant": item.variant,
                "quantity": item.quantity,
                "price": price,
                "subtotal": subtotal,
                "cart_item": item,
            }
        )
        total += subtotal

    if not items:
        messages.error(request, "Giỏ hàng trống, chưa thể thanh toán.")
        return redirect("cart:cart_detail")

    stock_errors = check_stock(items)
    if stock_errors:
        for err in stock_errors:
            messages.error(
                request,
                f'"{err["product"]}" chỉ còn {err["available"]} sản phẩm, bạn đặt {err["requested"]}.',
            )
        return redirect("cart:cart_detail")

    # Đọc voucher từ session
    voucher_code = request.session.get("voucher_code", "")
    voucher = None
    discount_amount = Decimal("0")
    if voucher_code:
        v = Voucher.objects.filter(code=voucher_code.upper(), is_active=True).first()
        if v:
            ok, _ = v.is_valid(total)
            if ok:
                voucher = v
                discount_amount = v.calc_discount(total)

    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            order = create_order_from_cart(
                request.user,
                request.session,
                form.cleaned_data,
                voucher=voucher,
            )
            if not order:
                messages.error(request, "Không thể tạo đơn hàng.")
                return redirect("cart:cart_detail")

            order.payment_method = Order.PaymentMethod.SEPAY
            order.sepay_invoice_number = order.code
            order.save(
                update_fields=["payment_method", "sepay_invoice_number", "updated_at"]
            )
            request.session.pop("voucher_code", None)

            success_url = request.build_absolute_uri(
                reverse("cart:sepay_return") + f"?order_code={order.code}"
            )
            error_url = request.build_absolute_uri(
                reverse("cart:sepay_return") + f"?order_code={order.code}&status=error"
            )
            cancel_url = request.build_absolute_uri(
                reverse("cart:sepay_return") + f"?order_code={order.code}&status=cancel"
            )
            customer_id = str(request.user.id) if request.user.is_authenticated else ""

            form_data = build_sepay_form_data(
                order,
                success_url=success_url,
                error_url=error_url,
                cancel_url=cancel_url,
                customer_id=customer_id,
            )

            return render(request, "sepay_redirect.html", {"form_data": form_data})
    else:
        initial = {}
        if request.user.is_authenticated:
            initial["email"] = getattr(request.user, "email", "") or ""
            if getattr(request.user, "first_name", "") or getattr(
                request.user, "last_name", ""
            ):
                initial["full_name"] = (
                    f"{request.user.first_name} {request.user.last_name}".strip()
                )
        form = CheckoutForm(initial=initial)

    final_total = total - discount_amount
    return render(
        request,
        "checkout.html",
        {
            "form": form,
            "cart_items": items,
            "total": total,
            "voucher": voucher,
            "discount_amount": discount_amount,
            "final_total": final_total,
            "voucher_code": voucher_code,
            "payment_method": "sepay",
        },
    )


def sepay_return(request):
    """
    SePay redirect về đây sau khi thanh toán (success / error / cancel).
    Production: trạng thái cập nhật qua IPN.
    Local (DEBUG=True): bypass IPN, mark PAID luôn khi status=success.
    """
    order_code = request.GET.get("order_code", "")
    status = request.GET.get("status", "success")

    order = Order.objects.filter(code=order_code).first()
    if not order:
        messages.error(request, "Không tìm thấy đơn hàng.")
        return redirect("cart:cart_detail")

    from django.conf import settings as _settings

    if status == "success":
        # Local dev: bypass IPN, tự động mark PAID + PROCESSING + trừ tồn kho
        if _settings.DEBUG and order.payment_status != Order.PaymentStatus.PAID:

            order.status = Order.Status.PAID
            order.payment_status = Order.PaymentStatus.PAID
            order.order_status = Order.OrderStatus.PROCESSING
            order.save(
                update_fields=[
                    "status",
                    "payment_status",
                    "order_status",
                    "updated_at",
                ]
            )

            order.log_status(
                Order.OrderStatus.PROCESSING,
                note="Thanh toán SePay thành công — chờ admin duyệt đơn và trừ tồn kho",
                actor="sepay_return_debug",
            )
            send_order_confirmation(order, request)
            clear_session_cart(request.session)
            if request.user.is_authenticated:
                clear_user_cart(request.user)
        messages.success(
            request,
            f"Đơn hàng {order.code} đã thanh toán thành công.",
        )
    elif status == "cancel":
        if order.status == Order.Status.PENDING:
            order.status = Order.Status.CANCELLED
            order.save(update_fields=["status", "updated_at"])
        messages.warning(request, f"Bạn đã hủy thanh toán đơn hàng {order.code}.")
    else:
        if order.status == Order.Status.PENDING:
            order.status = Order.Status.FAILED
            order.save(update_fields=["status", "updated_at"])
        messages.error(request, f"Thanh toán đơn hàng {order.code} thất bại.")

    return redirect("cart:order_detail", code=order.code)


@csrf_exempt
def sepay_ipn(request):
    """
    IPN endpoint — SePay POST JSON về đây khi có giao dịch.
    URL: /cart/sepay/ipn/
    Phải trả HTTP 200 để SePay không retry.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    if not verify_sepay_ipn(request):
        return JsonResponse({"error": "Unauthorized"}, status=401)

    try:
        data = parse_sepay_ipn(request.body)
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    notification_type = data.get("notification_type", "")
    order_data = data.get("order", {})
    invoice_number = order_data.get("order_invoice_number", "")

    order = Order.objects.filter(code=invoice_number).first()
    if not order:
        # Trả 200 để SePay không retry vô tận
        return JsonResponse({"success": True, "note": "order not found"})

    order.sepay_ipn_payload = str(data)
    order.sepay_status = order_data.get("order_status", "")

    if notification_type == "ORDER_PAID":
        transaction_data = data.get("transaction", {})
        if order.payment_status != Order.PaymentStatus.PAID:

            order.status = Order.Status.PAID
            order.payment_status = Order.PaymentStatus.PAID
            order.order_status = Order.OrderStatus.PROCESSING
            order.sepay_transaction_id = transaction_data.get("transaction_id", "")
            order.save(
                update_fields=[
                    "status",
                    "payment_status",
                    "order_status",
                    "sepay_transaction_id",
                    "sepay_status",
                    "sepay_ipn_payload",
                    "updated_at",
                ]
            )

            order.log_status(
                Order.OrderStatus.PROCESSING,
                note="Thanh toán SePay thành công — chờ admin duyệt đơn và trừ tồn kho",
                actor="sepay_ipn",
            )
            send_order_confirmation(order)
        else:
            order.save(
                update_fields=["sepay_status", "sepay_ipn_payload", "updated_at"]
            )

    elif notification_type == "TRANSACTION_VOID":
        order.status = Order.Status.CANCELLED
        order.order_status = Order.OrderStatus.CANCELLED
        order.save(
            update_fields=[
                "status",
                "order_status",
                "sepay_status",
                "sepay_ipn_payload",
                "updated_at",
            ]
        )

    else:
        order.save(update_fields=["sepay_status", "sepay_ipn_payload", "updated_at"])

    return JsonResponse({"success": True})
