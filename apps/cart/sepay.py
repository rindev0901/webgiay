"""
sepay.py - Tich hop Cong Thanh Toan SePay (sandbox + production).

Docs:
  https://developer.sepay.vn/vi/cong-thanh-toan/API/don-hang/form-thanh-toan
  https://developer.sepay.vn/vi/cong-thanh-toan/IPN
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json

from django.conf import settings


# Thu tu field khi tao signature - KHONG doi
_SIGN_FIELDS_ORDER = [
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
    Tao chu ky HMAC-SHA256 (base64) theo dung thu tu SePay quy dinh.
    Chi ky cac field co gia tri (khong None, khong rong).
    """
    parts = []
    for key in _SIGN_FIELDS_ORDER:
        val = fields.get(key)
        if val is not None and val != '':
            parts.append(f'{key}={val}')

    signed_string = ','.join(parts)
    raw_hmac = hmac.new(
        settings.SEPAY_SECRET_KEY.encode('utf-8'),
        signed_string.encode('utf-8'),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(raw_hmac).decode('utf-8')


def build_sepay_form_data(
    order,
    success_url: str,
    error_url: str,
    cancel_url: str,
    customer_id: str = '',
) -> dict:
    """
    Tra ve dict cac hidden field de render HTML form thanh toan SePay.
    Template phai render theo dung thu tu:
      order_amount, merchant, currency, operation,
      order_description, order_invoice_number, [customer_id],
      success_url, error_url, cancel_url, signature.
    """
    amount = int(order.total_amount)

    fields = {
        'order_amount':         str(amount),
        'merchant':             settings.SEPAY_MERCHANT,
        'currency':             'VND',
        'operation':            'PURCHASE',
        'order_description':    f'Thanh toan don hang {order.code}',
        'order_invoice_number': order.code,
        'success_url':          success_url,
        'error_url':            error_url,
        'cancel_url':           cancel_url,
    }

    if customer_id:
        fields['customer_id'] = customer_id

    fields['signature']    = _build_signature(fields)
    fields['checkout_url'] = settings.SEPAY_CHECKOUT_URL
    return fields


def verify_sepay_ipn(request) -> bool:
    """
    Xac thuc IPN tu SePay.
    - Auth Type = Secret Key: Header X-Secret-Key phai trung SEPAY_SECRET_KEY.
    - Auth Type = Khong co: luon True.
    """
    secret   = getattr(settings, 'SEPAY_SECRET_KEY', '')
    incoming = request.headers.get('X-Secret-Key', '')
    if incoming:
        return hmac.compare_digest(incoming, secret)
    return True


def parse_sepay_ipn(body: bytes) -> dict:
    """Parse JSON body tu IPN request."""
    return json.loads(body.decode('utf-8'))
