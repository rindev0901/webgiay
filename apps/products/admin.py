from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from .models import (
    Category, Brand, Color, Product,
    ProductVariant, ProductImage
)
from .resources import *   # Import tất cả Resource


# ====================== DANH MỤC ======================
@admin.register(Category)
class CategoryAdmin(ImportExportModelAdmin):
    list_display = ('name', 'slug', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('name',)


# ====================== THƯƠNG HIỆU ======================
@admin.register(Brand)
class BrandAdmin(ImportExportModelAdmin):
    list_display = ('name', 'slug', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}


# ====================== MÀU SẮC ======================
@admin.register(Color)
class ColorAdmin(admin.ModelAdmin):
    list_display = ('name', 'hex_code')
    search_fields = ('name',)


# ====================== INLINE CHO SẢN PHẨM ======================
class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 3
    max_num = 10


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1
    fields = ('size', 'color', 'sku', 'stock', 'price', 'is_active')  # ← Đã sửa trùng
    readonly_fields = ('sku',)


# ====================== SẢN PHẨM CHÍNH ======================
@admin.register(Product)
class ProductAdmin(ImportExportModelAdmin):
    resource_class = ProductResource

    list_display = ('name', 'brand', 'category', 'final_price_display',
                   'stock_status', 'featured', 'is_active')
    list_filter = ('category', 'brand', 'is_active', 'featured')
    search_fields = ('name', 'description', 'brand__name', 'category__name')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductVariantInline, ProductImageInline]

    fieldsets = (
        ('Thông tin cơ bản', {
            'fields': ('category', 'brand', 'name', 'slug', 'description')
        }),
        ('Giá cả', {
            'fields': ('price', 'discount_price')
        }),
        ('Trạng thái', {
            'fields': ('is_active', 'featured')
        }),
    )

    def final_price_display(self, obj):
        return obj.final_price
    final_price_display.short_description = "Giá bán"

    def stock_status(self, obj):
        total = sum(v.stock for v in obj.variants.all())
        return f"{total} đôi" if total > 0 else "Hết hàng"
    stock_status.short_description = "Tồn kho"


# ====================== BIẾN THỂ SẢN PHẨM ======================
@admin.register(ProductVariant)
class ProductVariantAdmin(ImportExportModelAdmin):
    list_display = ('product', 'size', 'color', 'sku', 'stock', 'price', 'is_active')
    list_filter = ('is_active', 'size', 'color')
    search_fields = ('product__name', 'sku')
    autocomplete_fields = ('product', 'color')


# ====================== HÌNH ẢNH SẢN PHẨM ======================
@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ('product', 'is_primary', 'alt_text')
    list_filter = ('is_primary',)
    search_fields = ('product__name',)
    autocomplete_fields = ('product',)


# ====================== Cấu hình Admin Site ======================
admin.site.site_header = "QUẢN TRỊ CỬA HÀNG GIÀY"
admin.site.site_title = "Admin Giày"
admin.site.index_title = "Trang quản trị"
