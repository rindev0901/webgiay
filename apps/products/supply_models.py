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
        DRAFT       = 'draft',       'Bản nháp'
        SENT        = 'sent',        'Đã gửi NCC'
        QUOTED      = 'quoted',      'NCC đã báo giá'
        APPROVED    = 'approved',    'Đã duyệt NCC'
        SHIPPED     = 'shipped',     'NCC đã giao hàng'
        IN_CHECKING = 'in_checking', 'Đang kiểm kê'
        CHECKED     = 'checked',     'Đã kiểm kê'
        RECEIVED    = 'received',    'Đã nhận hàng & thanh toán'
        CANCELLED   = 'cancelled',   'Đã hủy'

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


class InventoryCheck(models.Model):
    """Phiếu kiểm kê hàng nhập từ NCC."""
    class Status(models.TextChoices):
        PENDING   = 'pending',   'Chờ kiểm tra'
        CHECKING  = 'checking',  'Đang kiểm'
        COMPLETED = 'completed', 'Hoàn thành'
        APPROVED  = 'approved',  'Đã duyệt'
        REJECTED  = 'rejected',  'Từ chối'

    purchase_request = models.OneToOneField(
        PurchaseRequest, on_delete=models.CASCADE,
        related_name='inventory_check', verbose_name='Đợt đặt hàng'
    )
    code             = models.CharField(max_length=20, unique=True, blank=True, verbose_name='Mã phiếu')
    status           = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    # Người kiểm kê
    checker          = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='inventory_checks',
        verbose_name='Người kiểm kê'
    )
    checked_at       = models.DateTimeField(null=True, blank=True, verbose_name='Thời gian kiểm')

    # Người duyệt (cửa hàng trưởng)
    approved_by      = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='approved_inventory_checks',
        verbose_name='Người duyệt'
    )
    approved_at      = models.DateTimeField(null=True, blank=True, verbose_name='Thời gian duyệt')

    # Ghi chú
    note             = models.TextField(blank=True, verbose_name='Ghi chú chung')
    rejection_reason = models.TextField(blank=True, verbose_name='Lý do từ chối')

    # Tổng tiền thanh toán cho NCC
    total_amount     = models.DecimalField(
        max_digits=15, decimal_places=0, default=0,
        verbose_name='Tổng tiền thanh toán'
    )

    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Phiếu kiểm kê'
        verbose_name_plural = 'Phiếu kiểm kê'
        ordering = ['-created_at']
        permissions = [
            ('can_check_inventory', 'Có thể kiểm kê hàng'),
            ('can_approve_inventory', 'Có thể duyệt phiếu kiểm kê'),
        ]

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = f'IC{uuid.uuid4().hex[:8].upper()}'
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.code} - {self.get_status_display()}'


class InventoryCheckItem(models.Model):
    """Chi tiết từng mặt hàng trong phiếu kiểm kê."""
    inventory_check  = models.ForeignKey(
        InventoryCheck, on_delete=models.CASCADE,
        related_name='items', verbose_name='Phiếu kiểm kê'
    )
    variant          = models.ForeignKey('ProductVariant', on_delete=models.CASCADE)

    # Số lượng
    ordered_qty      = models.PositiveIntegerField(verbose_name='SL đặt hàng')
    received_qty     = models.PositiveIntegerField(default=0, verbose_name='SL thực nhận')

    # Giá
    unit_price       = models.DecimalField(max_digits=12, decimal_places=0, verbose_name='Đơn giá')
    total_price      = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name='Thành tiền')

    # Tình trạng
    is_matched       = models.BooleanField(default=True, verbose_name='Khớp đơn hàng')
    note             = models.CharField(max_length=500, blank=True, verbose_name='Ghi chú')

    # Hình ảnh kiểm tra (tùy chọn)
    image            = models.ImageField(
        upload_to='inventory_checks/', blank=True, null=True,
        verbose_name='Ảnh kiểm tra'
    )

    class Meta:
        unique_together = ('inventory_check', 'variant')
        verbose_name = 'Chi tiết kiểm kê'
        verbose_name_plural = 'Chi tiết kiểm kê'

    def save(self, *args, **kwargs):
        # Tự động tính thành tiền
        self.total_price = self.received_qty * self.unit_price
        # Kiểm tra khớp
        self.is_matched = (self.received_qty == self.ordered_qty)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.variant} - Đặt: {self.ordered_qty}, Nhận: {self.received_qty}'


class PaymentVoucher(models.Model):
    """Phiếu chi tiền cho NCC sau khi duyệt phiếu kiểm kê."""
    class Status(models.TextChoices):
        PENDING  = 'pending',  'Chờ thanh toán'
        PAID     = 'paid',     'Đã thanh toán'
        CANCELLED = 'cancelled', 'Đã hủy'

    inventory_check  = models.OneToOneField(
        InventoryCheck, on_delete=models.CASCADE,
        related_name='payment_voucher', verbose_name='Phiếu kiểm kê'
    )
    code             = models.CharField(max_length=20, unique=True, blank=True, verbose_name='Mã phiếu chi')
    supplier         = models.ForeignKey(Supplier, on_delete=models.CASCADE, verbose_name='Nhà cung cấp')

    amount           = models.DecimalField(max_digits=15, decimal_places=0, verbose_name='Số tiền')
    status           = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    payment_method   = models.CharField(max_length=100, blank=True, verbose_name='Phương thức thanh toán')
    payment_ref      = models.CharField(max_length=200, blank=True, verbose_name='Mã tham chiếu')

    created_by       = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_payment_vouchers'
    )
    paid_by          = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='paid_payment_vouchers',
        verbose_name='Người thanh toán'
    )
    paid_at          = models.DateTimeField(null=True, blank=True, verbose_name='Thời gian thanh toán')

    note             = models.TextField(blank=True, verbose_name='Ghi chú')

    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Phiếu chi tiền NCC'
        verbose_name_plural = 'Phiếu chi tiền NCC'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = f'PV{uuid.uuid4().hex[:8].upper()}'
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.code} - {self.supplier.name} - {int(self.amount):,}₫'
