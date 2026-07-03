from django.db import models
from django.utils.text import slugify
from django.core.validators import MinValueValidator
from typing import TYPE_CHECKING

# Re-export supply chain models so Django discovers them in this app
from .supply_models import (  # noqa: F401
    Supplier, PurchaseRequest, PurchaseRequestItem,
    SupplierQuote, SupplierQuoteItem,
    InventoryCheck, InventoryCheckItem, PaymentVoucher,
)

# ====================== 1. Danh mục & Thương hiệu ======================


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True,
                            verbose_name="Tên loại giày")
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True, verbose_name="Mô tả")
    image = models.ImageField(upload_to='categories/', blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Danh mục"
        verbose_name_plural = "Danh mục"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Brand(models.Model):
    name = models.CharField(max_length=100, unique=True,
                            verbose_name="Tên thương hiệu")
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    logo = models.ImageField(upload_to='brands/', blank=True, null=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Thương hiệu"
        verbose_name_plural = "Thương hiệu"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


# ====================== 2. Sản phẩm chính ======================
class Product(models.Model):
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name='products')
    brand = models.ForeignKey(
        Brand, on_delete=models.CASCADE, related_name='products')

    name = models.CharField(max_length=200, verbose_name="Tên sản phẩm")
    slug = models.SlugField(max_length=250, unique=True, blank=True)
    description = models.TextField(verbose_name="Mô tả chi tiết")

    price = models.DecimalField(
        max_digits=12, decimal_places=0, verbose_name="Giá gốc")
    discount_price = models.DecimalField(
        max_digits=12, decimal_places=0, blank=True, null=True, verbose_name="Giá khuyến mãi")

    is_active = models.BooleanField(default=True)
    featured = models.BooleanField(
        default=False, verbose_name="Sản phẩm nổi bật")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Sản phẩm"
        verbose_name_plural = "Sản phẩm"
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.brand} - {self.name}"

    @property
    def final_price(self):
        return self.discount_price if self.discount_price else self.price

    @property
    def discount_percent(self):
        """Tính phần trăm giảm giá (dùng trong template)"""
        # Check if both prices exist and are valid
        if not self.discount_price or not self.price:
            return 0

        try:
            # Convert to float for proper division
            discount_float = float(self.discount_price)
            price_float = float(self.price)

            # Validate positive values
            if discount_float <= 0 or price_float <= 0:
                return 0

            # Only show discount if discount_price is less than price
            if discount_float < price_float:
                percent = int((1 - discount_float / price_float) * 100)
                return percent if percent > 0 else 0
        except (ValueError, TypeError, ZeroDivisionError):
            return 0

        return 0

    @property
    def is_new(self):
        """Kiểm tra sản phẩm mới (trong vòng 30 ngày)"""
        from django.utils import timezone
        delta = timezone.now() - self.created_at
        return delta.days <= 30

    if TYPE_CHECKING:
        variants: models.Manager['ProductVariant']
        images: models.Manager['ProductImage']


# ====================== 3. Biến thể sản phẩm (Size + Màu) ======================
class Color(models.Model):
    name = models.CharField(max_length=50, unique=True)
    hex_code = models.CharField(
        max_length=7, blank=True, help_text="Ví dụ: #FF0000")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Màu sắc"
        verbose_name_plural = "Màu sắc"
        ordering = ['name']


class Size(models.Model):
    """Size giày: 35, 35.5, 36, 37, 37.5, 38, 38.5, 39, 40, 41, 42, 43, 44..."""
    name = models.CharField(max_length=10, unique=True, verbose_name="Size")
    order = models.PositiveSmallIntegerField(
        default=0, verbose_name="Thứ tự hiển thị",
        help_text="Số nhỏ hơn hiển thị trước (35 → 0, 35.5 → 1, 36 → 2...)"
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Kích thước"
        verbose_name_plural = "Kích thước"
        ordering = ['order', 'name']


class ProductVariant(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='variants')

    size = models.ForeignKey(
        Size, on_delete=models.CASCADE, verbose_name="Size",
        related_name='variants'
    )
    color = models.ForeignKey(
        Color, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Màu sắc"
    )

    sku = models.CharField(max_length=50, unique=True,
                           blank=True, verbose_name="Mã SKU")
    stock = models.PositiveIntegerField(default=0, verbose_name="Tồn kho")
    price = models.DecimalField(
        max_digits=12, decimal_places=0, blank=True, null=True,
        verbose_name="Giá (để trống = theo sản phẩm)")

    image = models.ImageField(
        upload_to='products/variants/', blank=True, null=True,
        verbose_name="Ảnh riêng")
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Biến thể"
        verbose_name_plural = "Biến thể"
        unique_together = ('product', 'size', 'color')
        ordering = ['size__order', 'size__name']

    def __str__(self):
        color_str = self.color.name if self.color else 'Mặc định'
        return f"{self.product.name} - Size {self.size.name} - {color_str}"

    @property
    def size_name(self):
        return self.size.name if self.size else ''

    def save(self, *args, **kwargs):
        if not self.sku:
            size_part = self.size.name if self.size else 'NA'
            color_part = self.color.name if self.color else 'N/A'
            self.sku = f"{self.product.slug}-{size_part}-{color_part}"
        if not self.price:
            self.price = self.product.final_price
        super().save(*args, **kwargs)


# ====================== 4. Hình ảnh sản phẩm (nhiều ảnh) ======================
class ProductImage(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/images/')
    alt_text = models.CharField(max_length=200, blank=True)
    is_primary = models.BooleanField(
        default=False,
        verbose_name="Ảnh đại diện",
        help_text="Ảnh hiển thị khi không chọn màu cụ thể"
    )
    color = models.ForeignKey(
        Color, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Màu sắc",
        help_text="Gắn ảnh với màu cụ thể. Để trống = ảnh chung cho tất cả màu.",
        related_name='images'
    )
    order = models.PositiveSmallIntegerField(
        default=0, verbose_name="Thứ tự",
        help_text="Số nhỏ hiển thị trước"
    )

    class Meta:
        verbose_name = "Hình ảnh sản phẩm"
        verbose_name_plural = "Hình ảnh sản phẩm"
        ordering = ['-is_primary', 'color', 'order']

    def __str__(self):
        color_str = f" [{self.color.name}]" if self.color else ""
        return f"Ảnh {self.product.name}{color_str}"


# ====================== 5. Lịch sử tồn kho ======================
class StockMovement(models.Model):
    class MovementType(models.TextChoices):
        IN      = 'in',      'Nhập kho'
        OUT     = 'out',     'Xuất kho (bán)'
        ADJUST  = 'adjust',  'Điều chỉnh'
        RETURN  = 'return',  'Trả hàng'
        CANCEL  = 'cancel',  'Huỷ đặt giữ'

    variant = models.ForeignKey(
        ProductVariant, on_delete=models.CASCADE,
        related_name='movements', verbose_name='Biến thể'
    )
    movement_type = models.CharField(
        max_length=10, choices=MovementType.choices, verbose_name='Loại'
    )
    quantity = models.IntegerField(
        verbose_name='Số lượng',
        help_text='Số dương = nhập vào, số âm = xuất ra'
    )
    stock_before = models.PositiveIntegerField(verbose_name='Tồn trước')
    stock_after  = models.PositiveIntegerField(verbose_name='Tồn sau')
    order_code   = models.CharField(max_length=32, blank=True, verbose_name='Mã đơn hàng')
    note         = models.CharField(max_length=255, blank=True, verbose_name='Ghi chú')
    created_by   = models.CharField(max_length=100, blank=True, verbose_name='Thực hiện bởi')
    created_at   = models.DateTimeField(auto_now_add=True, verbose_name='Thời gian')

    class Meta:
        verbose_name = 'Lịch sử tồn kho'
        verbose_name_plural = 'Lịch sử tồn kho'
        ordering = ['-created_at']

    def __str__(self):
        qty = int(self.quantity) if self.quantity is not None else 0
        return f"{self.get_movement_type_display()} | {self.variant} | {qty:+d}"

