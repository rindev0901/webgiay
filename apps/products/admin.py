from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum
from import_export.admin import ImportExportModelAdmin
from .models import (
    Category, Brand, Color, Size, Product,
    ProductVariant, ProductImage, StockMovement
)
from .resources import *   # Import tất cả Resource
from .inventory import adjust_stock


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


# ====================== SIZE ======================
@admin.register(Size)
class SizeAdmin(admin.ModelAdmin):
    list_display = ('name', 'order')
    search_fields = ('name',)
    ordering = ('order', 'name')


# ====================== INLINE CHO SẢN PHẨM ======================
# ====================== INLINE CHO SẢN PHẨM ======================
class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 2
    max_num = 30
    fields = ('image', 'image_preview', 'color', 'is_primary', 'order')
    readonly_fields = ('image_preview',)

    def image_preview(self, obj):
        from django.utils.html import format_html
        if obj.image:
            return format_html(
                '<img src="{}" style="height:60px;width:60px;object-fit:contain;'
                'border:1px solid #eee;border-radius:2px;" />',
                obj.image.url
            )
        return "—"
    image_preview.short_description = "Preview"


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1
    fields = ('size', 'color', 'sku', 'stock', 'price', 'is_active')
    readonly_fields = ('sku',)
    autocomplete_fields = ('size', 'color')


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
class StockMovementInline(admin.TabularInline):
    model = StockMovement
    extra = 0
    max_num = 0          # chỉ xem, không thêm từ inline
    can_delete = False
    readonly_fields = ('movement_type', 'quantity', 'stock_before',
                       'stock_after', 'order_code', 'note', 'created_by', 'created_at')
    ordering = ('-created_at',)


@admin.register(ProductVariant)
class ProductVariantAdmin(ImportExportModelAdmin):
    list_display  = ('product', 'size', 'color', 'sku', 'stock_badge', 'price', 'is_active')
    list_filter   = ('is_active', 'size', 'color', 'product__brand')
    search_fields = ('product__name', 'sku')
    autocomplete_fields = ('product', 'size', 'color')
    inlines = [StockMovementInline]
    readonly_fields = ('sku',)
    actions = ['mark_in_stock', 'mark_out_of_stock']

    def stock_badge(self, obj):
        if obj.stock == 0:
            return format_html('<span style="color:#dc2626;font-weight:700;">Hết hàng</span>')
        elif obj.stock <= 3:
            return format_html('<span style="color:#f59e0b;font-weight:700;">⚠ {}</span>', obj.stock)
        return format_html('<span style="color:#16a34a;font-weight:600;">{}</span>', obj.stock)
    stock_badge.short_description = 'Tồn kho'
    stock_badge.admin_order_field = 'stock'

    @admin.action(description='Đánh dấu hết hàng (stock=0)')
    def mark_out_of_stock(self, request, queryset):
        for v in queryset:
            if v.stock > 0:
                adjust_stock(v, -v.stock, note='Admin đánh dấu hết hàng',
                             actor=str(request.user))
        self.message_user(request, f'Đã cập nhật {queryset.count()} biến thể.')

    @admin.action(description='Nhập kho nhanh (+10 đôi)')
    def mark_in_stock(self, request, queryset):
        for v in queryset:
            adjust_stock(v, 10, note='Admin nhập kho nhanh +10',
                         actor=str(request.user))
        self.message_user(request, f'Đã nhập thêm 10 đôi cho {queryset.count()} biến thể.')


# ====================== LỊCH SỬ TỒN KHO ======================
@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display  = ('created_at', 'variant_display', 'movement_type_badge',
                     'quantity_display', 'stock_before', 'stock_after',
                     'order_code', 'created_by', 'note')
    list_filter   = ('movement_type', 'created_at', 'variant__product__brand')
    search_fields = ('variant__product__name', 'variant__sku', 'order_code', 'note')
    date_hierarchy = 'created_at'
    readonly_fields = [f.name for f in StockMovement._meta.fields]
    list_select_related = ('variant', 'variant__product', 'variant__size', 'variant__color')

    def has_add_permission(self, request):
        return False   # chỉ xem, không thêm thủ công qua admin list

    def variant_display(self, obj):
        return format_html(
            '<span style="font-size:12px;">{}<br>'
            '<small style="color:#888;">{}</small></span>',
            obj.variant.product.name[:40],
            f"Size {obj.variant.size.name}"
            + (f" / {obj.variant.color.name}" if obj.variant.color else '')
        )
    variant_display.short_description = 'Sản phẩm / Biến thể'

    def movement_type_badge(self, obj):
        colors = {
            'in':     '#16a34a',
            'out':    '#dc2626',
            'adjust': '#f59e0b',
            'return': '#1d6fb5',
            'cancel': '#888',
        }
        color = colors.get(obj.movement_type, '#555')
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;'
            'border-radius:2px;font-size:11px;font-weight:700;">{}</span>',
            color, obj.get_movement_type_display()
        )
    movement_type_badge.short_description = 'Loại'

    def quantity_display(self, obj):
        qty = int(obj.quantity) if obj.quantity is not None else 0
        color = '#16a34a' if qty > 0 else '#dc2626'
        return format_html(
            '<span style="color:{};font-weight:700;">{:+d}</span>',
            color, int(qty)
        )
    quantity_display.short_description = 'SL'


# ====================== HÌNH ẢNH SẢN PHẨM ======================
@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ('image_preview', 'product', 'color', 'is_primary', 'order', 'alt_text')
    list_filter = ('is_primary', 'color')
    search_fields = ('product__name', 'alt_text')
    autocomplete_fields = ('product',)
    list_select_related = ('product', 'color')
    ordering = ('product', 'color', 'order')

    def image_preview(self, obj):
        from django.utils.html import format_html
        if obj.image:
            return format_html(
                '<img src="{}" style="height:50px;width:50px;object-fit:contain;'
                'border:1px solid #eee;" />',
                obj.image.url
            )
        return "—"
    image_preview.short_description = "Ảnh"


# ====================== Cấu hình Admin Site ======================
admin.site.site_header = "QUẢN TRỊ CỬA HÀNG GIÀY"
admin.site.site_title = "Admin Giày"
admin.site.index_title = "Trang quản trị"
