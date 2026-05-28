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
    total_amount = models.DecimalField(max_digits=12, decimal_places=0, default=0)
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
