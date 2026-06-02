import uuid

from django.conf import settings
from django.db import models
from typing import TYPE_CHECKING

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
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=12, decimal_places=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('cart', 'product')

    def __str__(self):
        return f'{self.product} x {self.quantity}'

    @property
    def subtotal(self):
        return self.price * self.quantity


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Chờ thanh toán'
        PAID = 'paid', 'Đã thanh toán'
        FAILED = 'failed', 'Thanh toán thất bại'
        CANCELLED = 'cancelled', 'Đã hủy'

    class PaymentMethod(models.TextChoices):
        MOMO = 'momo', 'MoMo'
        COD = 'cod', 'COD'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders',
    )
    code = models.CharField(max_length=32, unique=True, blank=True)
    full_name = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=255, blank=True)
    note = models.TextField(blank=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name='Số tiền giảm')
    voucher = models.ForeignKey(
        'Voucher', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='orders', verbose_name='Voucher'
    )
    voucher_code = models.CharField(max_length=50, blank=True, verbose_name='Mã voucher (lưu lại)')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.MOMO)
    momo_order_id = models.CharField(max_length=100, blank=True, unique=True, null=True)
    momo_request_id = models.CharField(max_length=100, blank=True, unique=True, null=True)
    momo_trans_id = models.CharField(max_length=100, blank=True, null=True)
    momo_result_code = models.IntegerField(blank=True, null=True)
    momo_message = models.CharField(max_length=255, blank=True)
    momo_pay_url = models.URLField(blank=True)
    momo_response_payload = models.TextField(blank=True)
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


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.SET_NULL, null=True, blank=True)
    product_name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=12, decimal_places=0)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = 'Chi tiết đơn hàng'
        verbose_name_plural = 'Chi tiết đơn hàng'

    def __str__(self):
        return f'{self.product_name} x {self.quantity}'

    @property
    def subtotal(self):
        return self.price * self.quantity


# ====================== VOUCHER ======================
class Voucher(models.Model):
    class DiscountType(models.TextChoices):
        PERCENT = 'percent', 'Phần trăm (%)'
        FIXED   = 'fixed',   'Số tiền cố định (₫)'

    code = models.CharField(max_length=50, unique=True, verbose_name='Mã voucher')
    description = models.CharField(max_length=200, blank=True, verbose_name='Mô tả')

    discount_type = models.CharField(
        max_length=10, choices=DiscountType.choices,
        default=DiscountType.FIXED, verbose_name='Loại giảm'
    )
    discount_value = models.DecimalField(
        max_digits=12, decimal_places=0,
        verbose_name='Giá trị giảm',
        help_text='VD: 35000 (cố định) hoặc 10 (10%)'
    )
    min_order_amount = models.DecimalField(
        max_digits=12, decimal_places=0, default=0,
        verbose_name='Đơn tối thiểu (₫)'
    )
    max_discount_amount = models.DecimalField(
        max_digits=12, decimal_places=0, null=True, blank=True,
        verbose_name='Giảm tối đa (₫)',
        help_text='Chỉ áp dụng cho loại phần trăm. Để trống = không giới hạn.'
    )
    usage_limit = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Giới hạn lượt dùng',
        help_text='Để trống = không giới hạn'
    )
    used_count = models.PositiveIntegerField(default=0, verbose_name='Đã dùng')
    valid_from = models.DateTimeField(verbose_name='Hiệu lực từ')
    valid_to   = models.DateTimeField(verbose_name='Hết hạn')
    is_active  = models.BooleanField(default=True, verbose_name='Kích hoạt')

    class Meta:
        verbose_name = 'Phiếu giảm giá'
        verbose_name_plural = 'Phiếu giảm giá'
        ordering = ['-valid_to']

    def __str__(self):
        return self.code

    def calc_discount(self, order_total: 'Decimal') -> 'Decimal':
        """Tính số tiền thực tế được giảm cho order_total."""
        from decimal import Decimal
        if self.discount_type == self.DiscountType.PERCENT:
            amount = order_total * self.discount_value / Decimal('100')
            if self.max_discount_amount:
                amount = min(amount, self.max_discount_amount)
        else:
            amount = self.discount_value
        return min(amount, order_total)   # không giảm quá tổng đơn

    def is_valid(self, order_total: 'Decimal') -> tuple:
        """Kiểm tra hợp lệ, trả về (True/False, error_message)."""
        from django.utils import timezone
        from decimal import Decimal
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
