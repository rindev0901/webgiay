"""
sepay.py - Tich hop Cong Thanh Toan SePay.

Docs:
  https://developer.sepay.vn/vi/cong-thanh-toan/API/don-hang/form-thanh-toan
  https://developer.sepay.vn/vi/cong-thanh-toan/IPN
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

# Thu tu field ky PHAI trung khop thu tu input trong HTML form.
# Theo form mau SePay (khong doi thu tu nay):
#   order_amount, merchant, currency, operation,
#   order_description, order_invoice_number,
#   [customer_id - chi them neu co],
#   [payment_method - chi them neu co],
#   success_url, error_url, cancel_url
_SIGN_FIELDS_ORDERED = [
    'order_amount',
    'merchant',
    'currency',
    'operation',
    'order_description',
    'order_invoice_number',
    'customer_id',
    'payment_method',
    'success_url',
    'error_url',
    'cancel_url',
]


def _build_signature(fields: dict) -> str:
    """
    Tao chu ky HMAC-SHA256 (base64).
    Chi ky cac field co gia tri, theo dung thu tu _SIGN_FIELDS_ORDERED.
    """
    parts = []
    for key in _SIGN_FIELDS_ORDERED:
        val = fields.get(key)
        if val is not None and str(val).strip() != '':
            parts.append(f'{key}={val}')

    signed_string = ','.join(parts)
    logger.debug('[SePay] signed_string: %s', signed_string)

    raw_hmac = hmac.new(
        settings.SEPAY_SECRET_KEY.encode('utf-8'),
        signed_string.encode('utf-8'),
        hashlib.sha256,
    ).digest()
    sig = base64.b64encode(raw_hmac).decode('utf-8')
    logger.debug('[SePay] signature: %s', sig)
    return sig


def build_sepay_form_data(
    order,
    success_url: str,
    error_url: str,
    cancel_url: str,
    customer_id: str = '',
    payment_method: str = '',
) -> dict:
    """
    Tra ve dict cac field de render HTML form POST toi SePay.

    Thu tu render trong template PHAI la:
      order_amount, merchant, currency, operation,
      order_description, order_invoice_number,
      [customer_id], [payment_method],
      success_url, error_url, cancel_url,
      signature
    """
    # Dung so nguyen, khong co dau thap phan
    amount = str(int(order.total_amount))

    fields: dict = {
        'order_amount':         amount,
        'merchant':             settings.SEPAY_MERCHANT,
        'currency':             'VND',
        'operation':            'PURCHASE',
        'order_description':    f'Thanh toan don hang {order.code}',
        'order_invoice_number': order.code,
        'success_url':          success_url,
        'error_url':            error_url,
        'cancel_url':           cancel_url,
    }

    # Them optional fields neu co gia tri
    if customer_id:
        fields['customer_id'] = customer_id
    if payment_method:
        fields['payment_method'] = payment_method

    fields['signature']    = _build_signature(fields)
    fields['checkout_url'] = settings.SEPAY_CHECKOUT_URL
    return fields


def verify_sepay_ipn(request) -> bool:
    """
    Xac thuc IPN tu SePay.
    - Auth Type = Secret Key: Header X-Secret-Key phai trung SEPAY_SECRET_KEY.
    - Auth Type = Khong co   : luon True.
    """
    secret   = getattr(settings, 'SEPAY_SECRET_KEY', '')
    incoming = request.headers.get('X-Secret-Key', '')
    if incoming:
        return hmac.compare_digest(incoming, secret)
    return True


def parse_sepay_ipn(body: bytes) -> dict:
    """Parse JSON body tu IPN request."""
    return json.loads(body.decode('utf-8'))
