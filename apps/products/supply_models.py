"""Supply Chain models: Supplier, PurchaseRequest, SupplierQuote."""
import uuid
from django.conf import settings
from django.db import models


class Supplier(models.Model):
    name         = models.CharField(max_length=200, verbose_name='Tên NCC')
    contact_name = models.CharField(max_length=100, blank=True, verbose_name='Người liên hệ')
    phone        = models.CharField(max_length=20, blank=True)
    email        = models.EmailField(blank=True)
    address      = models.TextField(blank=True)
    note         = models.TextField(blank=True)
    is_active    = models.BooleanField(default=True)
    user         = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='supplier_profile',
        verbose_name='Tài khoản đăng nhập NCC',
    )
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Nhà cung cấp'
        verbose_name_plural = 'Nhà cung cấp'
        ordering = ['name']

    def __str__(self):
        return self.name


class PurchaseRequest(models.Model):
    class Status(models.TextChoices):
        DRAFT     = 'draft',     'Bản nháp'
        SENT      = 'sent',      'Đã gửi NCC'
        QUOTED    = 'quoted',    'NCC đã báo giá'
        APPROVED  = 'approved',  'Đã duyệt NCC'
        RECEIVED  = 'received',  'Đã nhận hàng'
        CANCELLED = 'cancelled', 'Đã hủy'

    code       = models.CharField(max_length=20, unique=True, blank=True)
    title      = models.CharField(max_length=200, default='Đợt thu mua bổ sung tồn kho')
    status     = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    note       = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='purchase_requests',
    )
    suppliers  = models.ManyToManyField(
        Supplier, blank=True, verbose_name='Gửi đến NCC',
    )
    approved_supplier = models.ForeignKey(
        Supplier, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='approved_requests', verbose_name='NCC được chọn',
    )
    approved_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='approved_requests',
    )
    approved_at  = models.DateTimeField(null=True, blank=True)
    deadline     = models.DateField(null=True, blank=True, verbose_name='Hạn báo giá')
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Đợt yêu cầu đặt hàng'
        verbose_name_plural = 'Đợt yêu cầu đặt hàng'
        ordering = ['-created_at']
        permissions = [
            ('can_approve_purchase', 'Có thể duyệt đặt hàng'),
            ('can_receive_goods',    'Có thể nhận hàng'),
        ]

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = f'PR{uuid.uuid4().hex[:8].upper()}'
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.code} — {self.title}'


class PurchaseRequestItem(models.Model):
    request       = models.ForeignKey(PurchaseRequest, on_delete=models.CASCADE, related_name='items')
    variant       = models.ForeignKey('ProductVariant', on_delete=models.CASCADE)
    current_stock = models.PositiveIntegerField(default=0, verbose_name='Tồn lúc tạo')
    requested_qty = models.PositiveIntegerField(verbose_name='SL yêu cầu')
    received_qty  = models.PositiveIntegerField(default=0, verbose_name='SL thực nhận')
    note          = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = ('request', 'variant')
        verbose_name = 'Chi tiết yêu cầu'
        verbose_name_plural = 'Chi tiết yêu cầu'

    def __str__(self):
        return f'{self.variant} × {self.requested_qty}'


class SupplierQuote(models.Model):
    request      = models.ForeignKey(PurchaseRequest, on_delete=models.CASCADE, related_name='quotes')
    supplier     = models.ForeignKey(Supplier, on_delete=models.CASCADE)
    submitted_at = models.DateTimeField(auto_now_add=True)
    note         = models.TextField(blank=True, verbose_name='Ghi chú từ NCC')
    csv_file     = models.FileField(
        upload_to='supplier_quotes/', blank=True, null=True,
        verbose_name='File CSV báo giá',
    )

    class Meta:
        unique_together = ('request', 'supplier')
        verbose_name = 'Báo giá NCC'
        verbose_name_plural = 'Báo giá NCC'

    def __str__(self):
        return f'{self.supplier} → {self.request.code}'


class SupplierQuoteItem(models.Model):
    quote         = models.ForeignKey(SupplierQuote, on_delete=models.CASCADE, related_name='items')
    variant       = models.ForeignKey('ProductVariant', on_delete=models.CASCADE)
    unit_price    = models.DecimalField(max_digits=12, decimal_places=0)
    available_qty = models.PositiveIntegerField(default=0)
    lead_days     = models.PositiveSmallIntegerField(default=3)

    class Meta:
        unique_together = ('quote', 'variant')

    def __str__(self):
        return f'{self.variant}: {int(self.unit_price):,}₫'
