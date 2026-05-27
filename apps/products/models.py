from django.db import models
from django.utils.text import slugify
from django.core.validators import MinValueValidator

# ====================== 1. Danh mục & Thương hiệu ======================
class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Tên loại giày")
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
    name = models.CharField(max_length=100, unique=True, verbose_name="Tên thương hiệu")
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
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name='products')
    
    name = models.CharField(max_length=200, verbose_name="Tên sản phẩm")
    slug = models.SlugField(max_length=250, unique=True, blank=True)
    description = models.TextField(verbose_name="Mô tả chi tiết")
    
    price = models.DecimalField(max_digits=12, decimal_places=0, verbose_name="Giá gốc")
    discount_price = models.DecimalField(max_digits=12, decimal_places=0, blank=True, null=True, verbose_name="Giá khuyến mãi")
    
    is_active = models.BooleanField(default=True)
    featured = models.BooleanField(default=False, verbose_name="Sản phẩm nổi bật")
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


# ====================== 3. Biến thể sản phẩm (Size + Màu) ======================
class Color(models.Model):
    name = models.CharField(max_length=50, unique=True)
    hex_code = models.CharField(max_length=7, blank=True, help_text="Ví dụ: #FF0000")

    def __str__(self):
        return self.name


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    
    size = models.CharField(max_length=20, verbose_name="Size")           # 36, 37, 38, 39, 40, 41, 42...
    color = models.ForeignKey(Color, on_delete=models.SET_NULL, null=True, blank=True)
    
    sku = models.CharField(max_length=50, unique=True, blank=True, verbose_name="Mã SKU")
    stock = models.PositiveIntegerField(default=0, verbose_name="Tồn kho")
    price = models.DecimalField(max_digits=12, decimal_places=0, blank=True, null=True)
    
    image = models.ImageField(upload_to='products/variants/', blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Biến thể"
        verbose_name_plural = "Biến thể"
        unique_together = ('product', 'size', 'color')

    def __str__(self):
        return f"{self.product.name} - Size {self.size} - {self.color}"

    def save(self, *args, **kwargs):
        if not self.sku:
            self.sku = f"{self.product.slug}-{self.size}-{self.color.name if self.color else 'N/A'}"
        if not self.price:
            self.price = self.product.final_price
        super().save(*args, **kwargs)


# ====================== 4. Hình ảnh sản phẩm (nhiều ảnh) ======================
class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/images/')
    alt_text = models.CharField(max_length=200, blank=True)
    is_primary = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Hình ảnh sản phẩm"
        verbose_name_plural = "Hình ảnh sản phẩm"
        ordering = ['-is_primary']

    def __str__(self):
        return f"Image of {self.product.name}"