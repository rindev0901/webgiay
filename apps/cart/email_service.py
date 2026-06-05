"""
email_service.py — Gửi email xác nhận đơn hàng.
"""
from __future__ import annotations
import logging
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.urls import reverse

logger = logging.getLogger(__name__)


def send_order_confirmation(order, request=None) -> bool:
    """
    Gửi email xác nhận đơn hàng cho khách.
    Trả về True nếu gửi thành công, False nếu thất bại.
    """
    recipient = order.email
    if not recipient:
        logger.warning(f"Order {order.code}: no email address, skipping confirmation email.")
        return False

    try:
        # Build order detail URL
        if request:
            order_detail_url = request.build_absolute_uri(
                reverse('cart:order_detail', kwargs={'code': order.code})
            )
        else:
            base_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
            order_detail_url = f"{base_url}/cart/orders/{order.code}/"

        context = {
            'order': order,
            'order_detail_url': order_detail_url,
        }

        # Render HTML template
        html_content = render_to_string('emails/order_confirmation.html', context)

        # Plain text fallback
        text_content = (
            f"Xác nhận đơn hàng #{order.code}\n\n"
            f"Xin chào {order.full_name},\n"
            f"Đơn hàng #{order.code} của bạn đã được thanh toán thành công.\n\n"
            f"Tổng tiền: {int(order.total_amount):,}₫\n"
            f"Phương thức: {order.get_payment_method_display()}\n\n"
            f"Xem chi tiết đơn hàng tại: {order_detail_url}\n\n"
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
        msg.send(fail_silently=False)

        logger.info(f"Order confirmation email sent to {recipient} for order {order.code}")
        return True

    except Exception as e:
        logger.error(f"Failed to send confirmation email for order {order.code}: {e}")
        return False
