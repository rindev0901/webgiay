"""
email_service.py — Gửi email xác nhận đơn hàng.
"""
from __future__ import annotations
import logging
import threading
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.urls import reverse

logger = logging.getLogger(__name__)


def _send_in_thread(order, order_detail_url: str) -> None:
    """Chạy trong background thread — không block request."""
    recipient = order.email
    try:
        context = {
            'order': order,
            'order_detail_url': order_detail_url,
        }
        html_content = render_to_string('emails/order_confirmation.html', context)
        text_content = (
            f"Xác nhận đơn hàng #{order.code}\n\n"
            f"Xin chào {order.full_name},\n"
            f"Đơn hàng #{order.code} của bạn đã được thanh toán thành công.\n\n"
            f"Tổng tiền: {int(order.total_amount):,}₫\n"
            f"Phương thức: {order.get_payment_method_display()}\n\n"
            f"Xem chi tiết: {order_detail_url}\n\n"
            f"Cảm ơn bạn đã mua sắm tại Dee Store!\n"
            f"Hotline: 0848 506 666"
        )
        subject = f"[Dee Store] Xác nhận đơn hàng #{order.code} - Thanh toán thành công"

        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient],
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=True)   # fail_silently=True — không crash nếu SMTP lỗi

        logger.info(f"[email] Confirmation sent to {recipient} for order {order.code}")

    except Exception as exc:
        # Bắt toàn bộ exception, chỉ log — không raise lên caller
        logger.error(f"[email] Failed for order {order.code}: {exc}")


def send_order_confirmation(order, request=None) -> None:
    """
    Gửi email xác nhận đơn hàng trong background thread.
    Không block request, không raise exception.
    """
    recipient = order.email
    if not recipient:
        logger.warning(f"[email] Order {order.code}: no email — skip.")
        return

    # Kiểm tra có cấu hình email chưa
    if not getattr(settings, 'EMAIL_HOST_USER', ''):
        logger.warning(f"[email] EMAIL_HOST_USER not configured — skip sending for {order.code}.")
        return

    # Build URL trước khi vào thread (request không thread-safe)
    if request:
        try:
            order_detail_url = request.build_absolute_uri(
                reverse('cart:order_detail', kwargs={'code': order.code})
            )
        except Exception:
            order_detail_url = _build_url(order)
    else:
        order_detail_url = _build_url(order)

    t = threading.Thread(
        target=_send_in_thread,
        args=(order, order_detail_url),
        daemon=True,
    )
    t.start()


def _build_url(order) -> str:
    base_url = getattr(settings, 'SITE_URL', 'http://localhost:8000').rstrip('/')
    return f"{base_url}/cart/orders/{order.code}/"
