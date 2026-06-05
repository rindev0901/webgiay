"""
email_service.py — Gửi email xác nhận đơn hàng qua Resend SDK.
"""
from __future__ import annotations
import logging
import threading
import resend
from django.template.loader import render_to_string
from django.conf import settings
from django.urls import reverse

logger = logging.getLogger(__name__)


def _send_in_thread(order, order_detail_url: str) -> None:
    """Chạy trong background thread — không block request."""
    recipient = order.email
    try:
        # Set API key
        resend.api_key = settings.RESEND_API_KEY

        # Render HTML template
        context = {
            'order': order,
            'order_detail_url': order_detail_url,
        }
        html_content = render_to_string('emails/order_confirmation.html', context)

        # Send via Resend SDK
        params: resend.Emails.SendParams = {
            "from": settings.DEFAULT_FROM_EMAIL,
            "to": [recipient],
            "subject": f"[Dat Shoes] Xác nhận đơn hàng #{order.code} - Thanh toán thành công",
            "html": html_content,
            "text": (
                f"Xác nhận đơn hàng #{order.code}\n\n"
                f"Xin chào {order.full_name},\n"
                f"Đơn hàng #{order.code} đã được thanh toán thành công.\n\n"
                f"Tổng tiền: {int(order.total_amount):,}₫\n"
                f"Phương thức: {order.get_payment_method_display()}\n\n"
                f"Xem chi tiết: {order_detail_url}\n\n"
                f"Cảm ơn bạn đã mua sắm tại Dat Shoes!\n"
                f"Hotline: 0848 506 666"
            ),
        }

        result = resend.Emails.send(params)
        logger.info(f"[email] Sent to {recipient} for order {order.code} — id: {result.get('id')}")

    except Exception as exc:
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

    if not getattr(settings, 'RESEND_API_KEY', ''):
        logger.warning(f"[email] RESEND_API_KEY not configured — skip for {order.code}.")
        return

    # Build URL before entering thread (request is not thread-safe)
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