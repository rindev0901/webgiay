"""
email_service.py — Gửi email xác nhận đơn hàng qua SMTP của Django.
Dùng cho chức năng: đặt hàng thành công -> gửi email xác nhận cho khách hàng.
"""

from __future__ import annotations

import logging
import threading

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse

logger = logging.getLogger(__name__)


def _send_in_thread(order, order_detail_url: str) -> None:
    """
    Hàm này chạy trong background thread.
    Mục đích: gửi email mà không làm request checkout bị chậm.
    """

    recipient = order.email

    try:
        # 1. Render file HTML email
        context = {
            "order": order,
            "order_detail_url": order_detail_url,
        }

        html_content = render_to_string(
            "emails/order_confirmation.html",
            context
        )

        # 2. Nội dung text dự phòng nếu email client không đọc HTML
        text_content = (
            f"Xác nhận đơn hàng #{order.code}\n\n"
            f"Xin chào {order.full_name},\n"
            f"Đơn hàng #{order.code} đã được thanh toán thành công.\n\n"
            f"Tổng tiền: {int(order.total_amount):,}₫\n"
            f"Phương thức: {order.get_payment_method_display()}\n\n"
            f"Xem chi tiết: {order_detail_url}\n\n"
            f"Cảm ơn bạn đã mua sắm tại Dat Shoes!\n"
            f"Hotline: 0987 654 321"
        )

        # 3. Tiêu đề email
        subject = f"[Dat Shoes] Xác nhận đơn hàng #{order.code} - Thanh toán thành công"

        # 4. Tạo email bằng SMTP backend của Django
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient],
        )

        # 5. Gắn thêm bản HTML
        email.attach_alternative(html_content, "text/html")

        # 6. Gửi email
        email.send(fail_silently=False)

        logger.info(f"[email] Sent to {recipient} for order {order.code}")

    except Exception as exc:
        logger.error(f"[email] Failed for order {order.code}: {exc}")


def send_order_confirmation(order, request=None) -> None:
    """
    Gửi email xác nhận đơn hàng trong background thread.
    Không block request checkout.
    Không raise exception ra ngoài để tránh làm lỗi đặt hàng.
    """

    recipient = order.email

    if not recipient:
        logger.warning(f"[email] Order {order.code}: no email — skip.")
        return

    if not getattr(settings, "EMAIL_HOST_USER", ""):
        logger.warning(f"[email] EMAIL_HOST_USER not configured — skip for {order.code}.")
        return

    if not getattr(settings, "EMAIL_HOST_PASSWORD", ""):
        logger.warning(f"[email] EMAIL_HOST_PASSWORD not configured — skip for {order.code}.")
        return

    # Build URL trước khi vào thread vì request không nên truyền sâu vào thread
    if request:
        try:
            order_detail_url = request.build_absolute_uri(
                reverse("cart:order_detail", kwargs={"code": order.code})
            )
        except Exception:
            order_detail_url = _build_url(order)
    else:
        order_detail_url = _build_url(order)

    thread = threading.Thread(
        target=_send_in_thread,
        args=(order, order_detail_url),
        daemon=True,
    )

    thread.start()


def _build_url(order) -> str:
    """
    Tạo link chi tiết đơn hàng khi không có request.
    Ví dụ:
    http://localhost:8000/cart/orders/OD123/
    """

    base_url = getattr(settings, "SITE_URL", "http://localhost:8000").rstrip("/")
    return f"{base_url}/cart/orders/{order.code}/"