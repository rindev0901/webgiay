import hashlib
import hmac
import json
import urllib.error
import urllib.request
from decimal import Decimal
from uuid import uuid4

from django.conf import settings


def _stringify_amount(amount):
    if isinstance(amount, Decimal):
        amount = int(amount)
    return str(amount)


def _build_create_signature(payload):
    raw = (
        f"accessKey={settings.MOMO_ACCESS_KEY}"
        f"&amount={payload['amount']}"
        f"&extraData={payload.get('extraData', '')}"
        f"&ipnUrl={payload['ipnUrl']}"
        f"&orderId={payload['orderId']}"
        f"&orderInfo={payload['orderInfo']}"
        f"&partnerCode={payload['partnerCode']}"
        f"&redirectUrl={payload['redirectUrl']}"
        f"&requestId={payload['requestId']}"
        f"&requestType={payload['requestType']}"
    )
    return hmac.new(
        settings.MOMO_SECRET_KEY.encode('utf-8'),
        raw.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()


def _build_result_signature(payload):
    raw = (
        f"accessKey={settings.MOMO_ACCESS_KEY}"
        f"&amount={payload.get('amount', '')}"
        f"&extraData={payload.get('extraData', '')}"
        f"&message={payload.get('message', '')}"
        f"&orderId={payload.get('orderId', '')}"
        f"&orderInfo={payload.get('orderInfo', '')}"
        f"&orderType={payload.get('orderType', '')}"
        f"&partnerCode={payload.get('partnerCode', '')}"
        f"&payType={payload.get('payType', '')}"
        f"&requestId={payload.get('requestId', '')}"
        f"&responseTime={payload.get('responseTime', '')}"
        f"&resultCode={payload.get('resultCode', '')}"
        f"&transId={payload.get('transId', '')}"
    )
    return hmac.new(
        settings.MOMO_SECRET_KEY.encode('utf-8'),
        raw.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()


def create_momo_payment(order, redirect_url, ipn_url):
    request_id = f'{order.code}-{uuid4().hex[:8]}'
    payload = {
        'partnerCode': settings.MOMO_PARTNER_CODE,
        'accessKey': settings.MOMO_ACCESS_KEY,
        'requestId': request_id,
        'amount': _stringify_amount(order.total_amount),
        'orderId': order.code,
        'orderInfo': f'Thanh toan don hang {order.code}',
        'redirectUrl': redirect_url,
        'ipnUrl': ipn_url,
        'extraData': '',
        'requestType': settings.MOMO_REQUEST_TYPE,
        'lang': 'vi',
    }
    payload['signature'] = _build_create_signature(payload)

    request = urllib.request.Request(
        settings.MOMO_ENDPOINT,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode('utf-8')
    except urllib.error.URLError as exc:
        raise RuntimeError(f'Không thể kết nối MoMo: {exc}') from exc

    result = json.loads(body)
    return payload, result


def verify_momo_signature(payload):
    expected = _build_result_signature(payload)
    return payload.get('signature') == expected


def get_payment_result_code(payload):
    try:
        return int(payload.get('resultCode'))
    except (TypeError, ValueError):
        return -1
