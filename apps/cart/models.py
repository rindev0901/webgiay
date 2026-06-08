import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models
from typing import TYPE_CHECKING


# ── Cart ──────────────────────────────────────────────────────
class Cart(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cart',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Cart of {self.user}'

    if TYPE_CHECKING:
        items: models.Manager['CartItem']


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='cart_items')
    variant = models.ForeignKey(
        'products.ProductVariant',
        on_delete=models.CASCADE,
        related_name='cart_items',
        null=True, blank=True,
        verbose_name='Biến thể (size/màu)',
    )
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=12, decimal_places=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('cart', 'product', 'variant')

    def __str__(self):
        variant_str = f' [{self.variant}]' if self.variant else ''
        return f'{self.product}{variant_str} x {self.quantity}'

    @property
    def subtotal(self):
        price = self.price if self.price is not None else Decimal("0")
        quantity = self.quantity if self.quantity is not None else 0
        return price * quantity


# ── Order ─────────────────────────────────────────────────────
class Order(models.Model):
    class Status(models.TextChoices):
        PENDING     = 'pending',     'Chờ thanh toán'
        PAID        = 'paid',        'Đã thanh toán'
        PROCESSING  = 'processing',  'Đang xử lý'
        SHIPPED     = 'shipped',     'Đang giao hàng'
        DELIVERED   = 'delivered',   'Đã giao hàng'
        FAILED      = 'failed',      'Thanh toán thất bại'
        CANCELLED   = 'cancelled',   'Đã hủy'

    class PaymentMethod(models.TextChoices):
        MOMO  = 'momo',  'MoMo'
        SEPAY = 'sepay', 'SePay'
        COD   = 'cod',   'COD'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='orders',
    )
    code        = models.CharField(max_length=32, unique=True, blank=True)
    full_name   = models.CharField(max_length=120, blank=True)
    phone       = models.CharField(max_length=20, blank=True)
    email       = models.EmailField(blank=True)
    address     = models.CharField(max_length=255, blank=True)
    note        = models.TextField(blank=True)

    total_amount    = models.DecimalField(max_digits=12, decimal_places=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name='Số tiền giảm')

    voucher      = models.ForeignKey('Voucher', on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    voucher_code = models.CharField(max_length=50, blank=True, verbose_name='Mã voucher (lưu lại)')

    status         = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.MOMO)

    # ── Delivery confirmation ──────────────────────
    delivered_at       = models.DateTimeField(null=True, blank=True, verbose_name='Thời gian nhận hàng')
    delivery_confirmed = models.BooleanField(default=False, verbose_name='Đã xác nhận nhận hàng')

    # ── MoMo ──────────────────────────────────────
    momo_order_id        = models.CharField(max_length=100, blank=True, unique=True, null=True)
    momo_request_id      = models.CharField(max_length=100, blank=True, unique=True, null=True)
    momo_trans_id        = models.CharField(max_length=100, blank=True, null=True)
    momo_result_code     = models.IntegerField(blank=True, null=True)
    momo_message         = models.CharField(max_length=255, blank=True)
    momo_pay_url         = models.URLField(blank=True)
    momo_response_payload = models.TextField(blank=True)

    # ── SePay ──────────────────────────────────────
    sepay_invoice_number = models.CharField(max_length=64, blank=True, verbose_name='SePay invoice number')
    sepay_transaction_id = models.CharField(max_length=100, blank=True, null=True, verbose_name='SePay transaction ID')
    sepay_pay_url        = models.URLField(blank=True, verbose_name='SePay checkout URL')
    sepay_status         = models.CharField(max_length=32, blank=True, verbose_name='SePay order status')
    sepay_ipn_payload    = models.TextField(blank=True, verbose_name='SePay IPN raw payload')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Đơn hàng'
        verbose_name_plural = 'Đơn hàng'

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = f'OD{uuid.uuid4().hex[:12].upper()}'
        super().save(*args, **kwargs)

    def __str__(self):
        return self.code

    def is_online_payment(self):
        return self.payment_method in (self.PaymentMethod.MOMO, self.PaymentMethod.SEPAY)

    def log_status(self, status, note='', actor='system'):
        """Helper: create a status log entry."""
        OrderStatusLog.objects.create(
            order=self, status=status, note=note, created_by=actor
        )


class OrderItem(models.Model):
    order        = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product      = models.ForeignKey('products.Product', on_delete=models.SET_NULL, null=True, blank=True)
    variant      = models.ForeignKey(
        'products.ProductVariant', on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name='Biến thể (size/màu)',
    )
    product_name = models.CharField(max_length=200)
    price        = models.DecimalField(max_digits=12, decimal_places=0)
    quantity     = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = 'Chi tiết đơn hàng'
        verbose_name_plural = 'Chi tiết đơn hàng'

    def __str__(self):
        return f'{self.product_name} x {self.quantity}'

    @property
    def subtotal(self):
        price = self.price if self.price is not None else Decimal("0")
        quantity = self.quantity if self.quantity is not None else 0
        return price * quantity


# ── Order Status Timeline ─────────────────────────────────────
class OrderStatusLog(models.Model):
    order      = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_logs')
    status     = models.CharField(max_length=20, choices=Order.Status.choices)
    note       = models.CharField(max_length=255, blank=True)
    created_by = models.CharField(max_length=100, blank=True, verbose_name='Thực hiện bởi')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Lịch sử trạng thái'
        verbose_name_plural = 'Lịch sử trạng thái'

    def __str__(self):
        return f'{self.order.code} → {self.get_status_display()}'


# ── Voucher ────────────────────────────────────────────────────
class Voucher(models.Model):
    class DiscountType(models.TextChoices):
        PERCENT = 'percent', 'Phần trăm (%)'
        FIXED   = 'fixed',   'Số tiền cố định (₫)'

    code                = models.CharField(max_length=50, unique=True, verbose_name='Mã voucher')
    description         = models.CharField(max_length=200, blank=True, verbose_name='Mô tả')
    discount_type       = models.CharField(max_length=10, choices=DiscountType.choices, default=DiscountType.FIXED)
    discount_value      = models.DecimalField(max_digits=12, decimal_places=0, verbose_name='Giá trị giảm')
    min_order_amount    = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    max_discount_amount = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True)
    usage_limit         = models.PositiveIntegerField(null=True, blank=True)
    used_count          = models.PositiveIntegerField(default=0)
    valid_from          = models.DateTimeField()
    valid_to            = models.DateTimeField()
    is_active           = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Phiếu giảm giá'
        verbose_name_plural = 'Phiếu giảm giá'
        ordering = ['-valid_to']

    def __str__(self):
        return self.code

    def calc_discount(self, order_total):
        from decimal import Decimal
        if self.discount_type == self.DiscountType.PERCENT:
            amount = order_total * self.discount_value / Decimal('100')
            if self.max_discount_amount:
                amount = min(amount, self.max_discount_amount)
        else:
            amount = self.discount_value
        return min(amount, order_total)

    def is_valid(self, order_total):
        from django.utils import timezone
        now = timezone.now()
        if not self.is_active:
            return False, 'Voucher không còn hoạt động.'
        if now < self.valid_from:
            return False, 'Voucher chưa đến thời gian sử dụng.'
        if now > self.valid_to:
            return False, 'Voucher đã hết hạn.'
        if self.usage_limit is not None and self.used_count >= self.usage_limit:
            return False, 'Voucher đã hết lượt sử dụng.'
        if order_total < self.min_order_amount:
            return False, f'Đơn hàng tối thiểu {int(self.min_order_amount):,}₫ để dùng voucher này.'
        return True, ''
