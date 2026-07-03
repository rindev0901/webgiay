from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline
from unfold.paginator import InfinitePaginator
from import_export.admin import ImportExportModelAdmin
from import_export.forms import ImportForm, ConfirmImportForm

from .models import (
    Category,
    Brand,
    Color,
    Size,
    Product,
    ProductVariant,
    ProductImage,
    StockMovement,
    Supplier,
    InventoryCheck,
    InventoryCheckItem,
    PaymentVoucher,
)
from .resources import *
from .inventory import adjust_stock


class SupplySidebarHiddenMixin:
    """Ẩn model khỏi All applications — chỉ hiện trong menu Chuỗi cung ứng."""

    def has_module_permission(self, request):
        return False


# ====================== DANH MỤC ======================
# Register the Giay model with the admin site


@admin.register(Category)
class CategoryAdmin(ImportExportModelAdmin, ModelAdmin):
    list_display = ("name", "slug", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)
    list_per_page = 20
    paginator = InfinitePaginator


# ====================== THƯƠNG HIỆU ======================
@admin.register(Brand)
class BrandAdmin(ImportExportModelAdmin, ModelAdmin):
    list_display = ("name", "slug", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}
    list_per_page = 20
    paginator = InfinitePaginator


# ====================== MÀU SẮC ======================
@admin.register(Color)
class ColorAdmin(ModelAdmin):
    list_display = ("name", "hex_code")
    search_fields = ("name",)
    list_per_page = 30
    paginator = InfinitePaginator


# ====================== SIZE ======================
@admin.register(Size)
class SizeAdmin(ModelAdmin):
    list_display = ("name", "order")
    search_fields = ("name",)
    ordering = ("order", "name")
    list_per_page = 30
    paginator = InfinitePaginator


# ====================== INLINE CHO SẢN PHẨM ======================
class ProductImageInline(TabularInline):
    model = ProductImage
    extra = 2
    max_num = 30
    fields = ("image", "image_preview", "color", "is_primary", "order")
    readonly_fields = ("image_preview",)

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height:60px;width:60px;object-fit:contain;'
                'border:1px solid #eee;border-radius:2px;" />',
                obj.image.url,
            )
        return "—"

    image_preview.short_description = "Preview"


class ProductVariantInline(TabularInline):
    model = ProductVariant
    extra = 1
    fields = ("size", "color", "sku", "stock", "price", "is_active")
    readonly_fields = ("sku",)
    autocomplete_fields = ("size", "color")


# ====================== SẢN PHẨM CHÍNH ======================
@admin.register(Product)
class ProductAdmin(ImportExportModelAdmin, ModelAdmin):
    resource_class = ProductResource
    change_list_template = "admin/products/product_changelist.html"

    list_display = (
        "name",
        "brand",
        "category",
        "final_price_display",
        "stock_status",
        "featured",
        "is_active",
    )
    list_filter = ("category", "brand", "is_active", "featured")
    search_fields = ("name", "description", "brand__name", "category__name")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ProductVariantInline, ProductImageInline]
    list_per_page = 20
    paginator = InfinitePaginator

    fieldsets = (
        (
            "Thông tin cơ bản",
            {"fields": ("category", "brand", "name", "slug", "description")},
        ),
        ("Giá cả", {"fields": ("price", "discount_price")}),
        ("Trạng thái", {"fields": ("is_active", "featured")}),
    )

    def final_price_display(self, obj):
        return obj.final_price

    final_price_display.short_description = "Giá bán"

    def stock_status(self, obj):
        total = sum(v.stock for v in obj.variants.all())
        return f"{total} đôi" if total > 0 else "Hết hàng"

    stock_status.short_description = "Tồn kho"


# ====================== BIẾN THỂ ======================
class StockMovementInline(TabularInline):
    model = StockMovement
    extra = 0
    max_num = 0
    can_delete = False
    readonly_fields = (
        "movement_type",
        "quantity",
        "stock_before",
        "stock_after",
        "order_code",
        "note",
        "created_by",
        "created_at",
    )
    ordering = ("-created_at",)


@admin.register(ProductVariant)
class ProductVariantAdmin(ImportExportModelAdmin, ModelAdmin):
    list_display = (
        "product",
        "size",
        "color",
        "sku",
        "stock_badge",
        "price",
        "is_active",
    )
    list_filter = ("is_active", "size", "color", "product__brand")
    search_fields = ("product__name", "sku")
    autocomplete_fields = ("product", "size", "color")
    inlines = [StockMovementInline]
    readonly_fields = ("sku",)
    actions = ["mark_in_stock", "mark_out_of_stock", "go_to_stock_in"]
    list_per_page = 25
    paginator = InfinitePaginator

    def stock_badge(self, obj):
        if obj.stock == 0:
            return format_html(
                '<span style="color:#dc2626;font-weight:700;">Hết hàng</span>'
            )
        elif obj.stock <= 3:
            return format_html(
                '<span style="color:#f59e0b;font-weight:700;">⚠ {}</span>', obj.stock
            )
        return format_html(
            '<span style="color:#16a34a;font-weight:600;">{}</span>', obj.stock
        )

    stock_badge.short_description = "Tồn kho"
    stock_badge.admin_order_field = "stock"

    @admin.action(description="Đánh dấu hết hàng (stock=0)")
    def mark_out_of_stock(self, request, queryset):
        for v in queryset:
            if v.stock > 0:
                adjust_stock(
                    v, -v.stock, note="Admin đánh dấu hết hàng", actor=str(request.user)
                )
        self.message_user(request, f"Đã cập nhật {queryset.count()} biến thể.")

    @admin.action(description="Nhập kho nhanh (+10 đôi)")
    def mark_in_stock(self, request, queryset):
        for v in queryset:
            adjust_stock(
                v, 10, note="Admin nhập kho nhanh +10", actor=str(request.user)
            )
        self.message_user(
            request, f"Đã nhập thêm 10 đôi cho {queryset.count()} biến thể."
        )

    @admin.action(description="🔽 Mở trang Nhập kho hàng")
    def go_to_stock_in(self, request, queryset):
        from django.http import HttpResponseRedirect
        from django.urls import reverse

        return HttpResponseRedirect(reverse("products:stock_in"))


# ====================== LỊCH SỬ TỒN KHO ======================
@admin.register(StockMovement)
class StockMovementAdmin(SupplySidebarHiddenMixin, ModelAdmin):
    list_display = (
        "created_at",
        "variant_display",
        "movement_type_badge",
        "quantity_display",
        "stock_before",
        "stock_after",
        "order_code",
        "created_by",
        "note",
    )
    list_filter = ("movement_type", "created_at", "variant__product__brand")
    search_fields = ("variant__product__name", "variant__sku", "order_code", "note")
    date_hierarchy = "created_at"
    readonly_fields = [f.name for f in StockMovement._meta.fields]
    list_per_page = 30
    paginator = InfinitePaginator
    list_select_related = (
        "variant",
        "variant__product",
        "variant__size",
        "variant__color",
    )

    def has_add_permission(self, request):
        return False

    def variant_display(self, obj):
        return format_html(
            '<span style="font-size:12px;">{}<br>'
            '<small style="color:#888;">{}</small></span>',
            obj.variant.product.name[:40],
            f"Size {obj.variant.size.name}"
            + (f" / {obj.variant.color.name}" if obj.variant.color else ""),
        )

    variant_display.short_description = "Sản phẩm / Biến thể"

    def movement_type_badge(self, obj):
        colors = {
            "in": "#16a34a",
            "out": "#dc2626",
            "adjust": "#f59e0b",
            "return": "#1d6fb5",
            "cancel": "#888",
        }
        color = colors.get(obj.movement_type, "#555")
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;'
            'border-radius:2px;font-size:11px;font-weight:700;">{}</span>',
            color,
            obj.get_movement_type_display(),
        )

    movement_type_badge.short_description = "Loại"

    def quantity_display(self, obj):
        qty = int(obj.quantity) if obj.quantity is not None else 0
        color = "#16a34a" if qty > 0 else "#dc2626"
        return format_html(
            '<span style="color:{};font-weight:700;">{}</span>', color, f"{qty:+d}"
        )

    quantity_display.short_description = "SL"


# ====================== HÌNH ẢNH ======================
@admin.register(ProductImage)
class ProductImageAdmin(ModelAdmin):
    list_display = (
        "image_preview",
        "product",
        "color",
        "is_primary",
        "order",
        "alt_text",
    )
    list_filter = ("is_primary", "color")
    search_fields = ("product__name", "alt_text")
    autocomplete_fields = ("product",)
    list_select_related = ("product", "color")
    ordering = ("product", "color", "order")
    list_per_page = 30
    paginator = InfinitePaginator

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height:50px;width:50px;object-fit:contain;'
                'border:1px solid #eee;" />',
                obj.image.url,
            )
        return "—"

    image_preview.short_description = "Ảnh"


# ====================== CHUỖI CUNG ỨNG — SupplierAdmin (cuối file) ======================
@admin.register(Supplier)
class SupplierAdmin(SupplySidebarHiddenMixin, ModelAdmin):
    list_display = ('name', 'contact_name', 'phone', 'email', 'is_active', 'user')
    list_filter = ('is_active',)
    search_fields = ('name', 'contact_name', 'email', 'phone')
    autocomplete_fields = ('user',)
    list_per_page = 20
    paginator = InfinitePaginator


# ====================== INVENTORY CHECK ======================
class InventoryCheckItemInline(TabularInline):
    model = InventoryCheckItem
    extra = 0
    fields = ('variant', 'ordered_qty', 'received_qty', 'unit_price', 'total_price', 'is_matched', 'note')
    readonly_fields = ('total_price', 'is_matched')
    can_delete = False


@admin.register(InventoryCheck)
class InventoryCheckAdmin(SupplySidebarHiddenMixin, ModelAdmin):
    list_display = (
        'code',
        'purchase_request',
        'supplier_name',
        'status_badge',
        'checker',
        'approved_by',
        'total_amount_display',
        'created_at',
    )
    list_filter = ('status', 'created_at')
    search_fields = ('code', 'purchase_request__code', 'purchase_request__approved_supplier__name')
    readonly_fields = ('code', 'purchase_request', 'total_amount', 'created_at', 'updated_at')
    inlines = [InventoryCheckItemInline]
    list_per_page = 20
    paginator = InfinitePaginator
    list_select_related = ('purchase_request', 'purchase_request__approved_supplier', 'checker', 'approved_by')

    fieldsets = (
        ('Thông tin cơ bản', {
            'fields': ('code', 'purchase_request', 'status', 'note')
        }),
        ('Kiểm kê', {
            'fields': ('checker', 'checked_at')
        }),
        ('Duyệt', {
            'fields': ('approved_by', 'approved_at', 'rejection_reason')
        }),
        ('Tài chính', {
            'fields': ('total_amount',)
        }),
        ('Thời gian', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    def supplier_name(self, obj):
        if obj.purchase_request and obj.purchase_request.approved_supplier:
            return obj.purchase_request.approved_supplier.name
        return '—'
    supplier_name.short_description = 'Nhà cung cấp'

    def status_badge(self, obj):
        colors = {
            'pending': '#f59e0b',
            'checking': '#3b82f6',
            'completed': '#8b5cf6',
            'approved': '#16a34a',
            'rejected': '#dc2626',
        }
        color = colors.get(obj.status, '#888')
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;'
            'border-radius:2px;font-size:11px;font-weight:700;">{}</span>',
            color,
            obj.get_status_display(),
        )
    status_badge.short_description = 'Trạng thái'

    def total_amount_display(self, obj):
        return format_html(
            '<span style="font-weight:600;">{:,}₫</span>',
            int(obj.total_amount)
        )
    total_amount_display.short_description = 'Tổng tiền'
    total_amount_display.admin_order_field = 'total_amount'

    def has_add_permission(self, request):
        # Chỉ tạo từ flow, không cho tạo thủ công
        return False


@admin.register(InventoryCheckItem)
class InventoryCheckItemAdmin(SupplySidebarHiddenMixin, ModelAdmin):
    list_display = (
        'inventory_check',
        'variant',
        'ordered_qty',
        'received_qty',
        'matched_badge',
        'unit_price',
        'total_price_display',
    )
    list_filter = ('is_matched', 'inventory_check__status')
    search_fields = ('inventory_check__code', 'variant__product__name', 'variant__sku')
    readonly_fields = ('total_price', 'is_matched')
    list_per_page = 30
    paginator = InfinitePaginator
    list_select_related = ('inventory_check', 'variant', 'variant__product')

    def matched_badge(self, obj):
        if obj.is_matched:
            return format_html(
                '<span style="color:#16a34a;font-weight:700;">✓ Khớp</span>'
            )
        return format_html(
            '<span style="color:#dc2626;font-weight:700;">✗ Lệch</span>'
        )
    matched_badge.short_description = 'Khớp đơn'

    def total_price_display(self, obj):
        return format_html(
            '<span style="font-weight:600;">{:,}₫</span>',
            int(obj.total_price)
        )
    total_price_display.short_description = 'Thành tiền'

    def has_add_permission(self, request):
        return False


# ====================== PAYMENT VOUCHER ======================
@admin.register(PaymentVoucher)
class PaymentVoucherAdmin(SupplySidebarHiddenMixin, ModelAdmin):
    list_display = (
        'code',
        'supplier',
        'amount_display',
        'status_badge',
        'payment_method',
        'paid_by',
        'paid_at',
        'created_at',
    )
    list_filter = ('status', 'created_at', 'paid_at')
    search_fields = ('code', 'supplier__name', 'payment_ref', 'inventory_check__code')
    readonly_fields = ('code', 'inventory_check', 'supplier', 'amount', 'created_at', 'updated_at')
    list_per_page = 20
    paginator = InfinitePaginator
    list_select_related = ('supplier', 'inventory_check', 'created_by', 'paid_by')

    fieldsets = (
        ('Thông tin cơ bản', {
            'fields': ('code', 'inventory_check', 'supplier', 'amount', 'status')
        }),
        ('Thanh toán', {
            'fields': ('payment_method', 'payment_ref', 'paid_by', 'paid_at')
        }),
        ('Ghi chú', {
            'fields': ('note',)
        }),
        ('Thời gian', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    def status_badge(self, obj):
        colors = {
            'pending': '#f59e0b',
            'paid': '#16a34a',
            'cancelled': '#888',
        }
        color = colors.get(obj.status, '#888')
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;'
            'border-radius:2px;font-size:11px;font-weight:700;">{}</span>',
            color,
            obj.get_status_display(),
        )
    status_badge.short_description = 'Trạng thái'

    def amount_display(self, obj):
        return format_html(
            '<span style="font-weight:700;font-size:13px;">{:,}₫</span>',
            int(obj.amount)
        )
    amount_display.short_description = 'Số tiền'
    amount_display.admin_order_field = 'amount'

    def has_add_permission(self, request):
        # Chỉ tạo từ flow, không cho tạo thủ công
        return False


# ====================== Admin site config ======================
admin.site.site_header = "QUẢN TRỊ CỬA HÀNG GIÀY"
admin.site.site_title = "Admin Giày"
admin.site.index_title = "Trang quản trị"

