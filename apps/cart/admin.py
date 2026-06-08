from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from django.conf import settings
from unfold.admin import ModelAdmin, TabularInline
from .models import Order, OrderItem, OrderStatusLog, Voucher, CartItem, Cart
from apps.products.inventory import deduct_stock, restore_stock


# ── Inlines ───────────────────────────────────────────────────
class OrderItemInline(TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product_name', 'product', 'variant', 'price', 'quantity', 'subtotal')
    fields = ('product_name', 'variant', 'quantity', 'price', 'subtotal')

    def subtotal_display(self, obj):
        subtotal = obj.subtotal or 0
        return f"{int(subtotal):,}₫".replace(',', '.')

    subtotal_display.short_description = "Thành tiền"


class OrderStatusLogInline(TabularInline):
    model = OrderStatusLog
    extra = 0
    max_num = 0
    can_delete = False
    readonly_fields = ('created_at', 'status', 'note', 'created_by')
    ordering = ('created_at',)


# ── Order Admin ───────────────────────────────────────────────
@admin.register(Order)
class OrderAdmin(ModelAdmin):
    list_display = (
        'code', 'full_name', 'status_badge', 'payment_method',
        'total_amount_display', 'delivery_badge', 'created_at',
    )
    list_filter  = ('status', 'payment_method', 'delivery_confirmed', 'created_at')
    search_fields = ('code', 'full_name', 'phone', 'email')
    inlines = [OrderItemInline, OrderStatusLogInline]
    readonly_fields = ('code', 'created_at', 'updated_at', 'delivered_at', 'qr_preview')
    actions = [
        'action_mark_processing',
        'action_mark_shipped',
        'action_approve_and_deduct',
        'action_cancel_and_restore',
    ]

    fieldsets = (
        ('Thông tin đơn hàng', {
            'fields': ('code', 'status', 'payment_method', 'created_at', 'updated_at')
        }),
        ('Khách hàng', {
            'fields': ('user', 'full_name', 'phone', 'email', 'address', 'note')
        }),
        ('Thanh toán', {
            'fields': ('total_amount', 'discount_amount', 'voucher', 'voucher_code')
        }),
        ('Giao hàng', {
            'fields': ('delivery_confirmed', 'delivered_at', 'qr_preview')
        }),
    )

    def status_badge(self, obj):
        colors = {
            'pending':    ('#f59e0b', '#1c1917'),
            'paid':       ('#22c55e', '#fff'),
            'processing': ('#3b82f6', '#fff'),
            'shipped':    ('#8b5cf6', '#fff'),
            'delivered':  ('#16a34a', '#fff'),
            'failed':     ('#ef4444', '#fff'),
            'cancelled':  ('#9ca3af', '#fff'),
        }
        bg, fg = colors.get(obj.status, ('#ddd', '#333'))
        return format_html(
            '<span style="background:{};color:{};padding:3px 10px;border-radius:12px;font-size:11px;font-weight:700;">{}</span>',
            bg, fg, obj.get_status_display()
        )
    status_badge.short_description = 'Trạng thái'

    def delivery_badge(self, obj):
        if obj.delivery_confirmed:
            return format_html('<span style="color:#16a34a;font-weight:700;">✓ Đã nhận</span>')
        elif obj.status == 'shipped':
            return format_html('<span style="color:#8b5cf6;">Đang giao</span>')
        return format_html('<span style="color:#9ca3af;">—</span>')
    delivery_badge.short_description = 'Giao hàng'

    def total_amount_display(self, obj):
        return f"{int(obj.total_amount):,}₫".replace(',', '.')
    total_amount_display.short_description = 'Tổng tiền'

    def qr_preview(self, obj):
        """Show QR code in admin detail view."""
        if not obj.pk:
            return '—'
        from django.urls import reverse
        base_url = getattr(settings, 'SITE_URL', 'http://localhost:8000').rstrip('/')
        confirm_url = f"{base_url}/cart/orders/{obj.code}/confirm-delivery/"
        try:
            import qrcode, io, base64
            qr = qrcode.QRCode(version=1, box_size=6, border=2)
            qr.add_data(confirm_url)
            qr.make(fit=True)
            img = qr.make_image(fill_color='black', back_color='white')
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            b64 = base64.b64encode(buf.getvalue()).decode()
            return format_html(
                '<img src="data:image/png;base64,{}" style="width:150px;height:150px;" />'
                '<br><small style="color:#888;">Quét để xác nhận giao hàng</small>',
                b64
            )
        except Exception:
            return format_html('<a href="{}" target="_blank">{}</a>', confirm_url, confirm_url)
    qr_preview.short_description = 'QR giao hàng'

    # ── Admin Actions ─────────────────────────────────────────

    @admin.action(description='✅ Duyệt đơn + trừ tồn kho (online đã TT)')
    def action_approve_and_deduct(self, request, queryset):
        count = 0
        for order in queryset.filter(
            status__in=[Order.Status.PAID, Order.Status.PENDING],
            payment_method__in=[Order.PaymentMethod.MOMO, Order.PaymentMethod.SEPAY]
        ):
            errors = deduct_stock(order, actor=str(request.user))
            if not errors:
                order.status = Order.Status.PROCESSING
                order.save(update_fields=['status', 'updated_at'])
                order.log_status(Order.Status.PROCESSING, note='Admin duyệt đơn', actor=str(request.user))
                count += 1
        self.message_user(request, f'Đã duyệt {count} đơn hàng.')

    @admin.action(description='🚚 Chuyển sang Đang giao hàng')
    def action_mark_shipped(self, request, queryset):
        count = 0
        for order in queryset.filter(status=Order.Status.PROCESSING):
            order.status = Order.Status.SHIPPED
            order.save(update_fields=['status', 'updated_at'])
            order.log_status(Order.Status.SHIPPED, note='Đã bàn giao shipper', actor=str(request.user))
            count += 1
        self.message_user(request, f'Đã cập nhật {count} đơn sang "Đang giao hàng".')

    @admin.action(description='⚙️ Chuyển sang Đang xử lý')
    def action_mark_processing(self, request, queryset):
        count = 0
        for order in queryset.filter(status__in=[Order.Status.PAID, Order.Status.PENDING]):
            order.status = Order.Status.PROCESSING
            order.save(update_fields=['status', 'updated_at'])
            order.log_status(Order.Status.PROCESSING, note='Admin chuyển trạng thái', actor=str(request.user))
            count += 1
        self.message_user(request, f'Đã cập nhật {count} đơn.')

    @admin.action(description='❌ Hủy đơn + hoàn tồn kho')
    def action_cancel_and_restore(self, request, queryset):
        count = 0
        for order in queryset.exclude(status__in=[Order.Status.DELIVERED, Order.Status.CANCELLED]):
            restore_stock(order, actor=str(request.user))
            order.status = Order.Status.CANCELLED
            order.save(update_fields=['status', 'updated_at'])
            order.log_status(Order.Status.CANCELLED, note='Admin hủy đơn', actor=str(request.user))
            count += 1
        self.message_user(request, f'Đã hủy {count} đơn và hoàn tồn kho.')


# @admin.register(OrderItem)
class OrderItemAdmin(ModelAdmin):
    list_display = ('order', 'product_name', 'variant', 'quantity', 'price')


@admin.register(Voucher)
class VoucherAdmin(ModelAdmin):
    list_display  = ('code', 'discount_type', 'discount_value', 'min_order_amount',
                     'used_count', 'usage_limit', 'valid_from', 'valid_to',
                     'is_active', 'is_expired')
    list_filter   = ('discount_type', 'is_active')
    search_fields = ('code', 'description')
    readonly_fields = ('used_count',)
    list_editable = ('is_active',)
    ordering = ('-valid_to',)

    fieldsets = (
        ('Thông tin cơ bản', {
            'fields': ('code', 'description', 'is_active')
        }),
        ('Giảm giá', {
            'fields': ('discount_type', 'discount_value',
                       'min_order_amount', 'max_discount_amount')
        }),
        ('Giới hạn sử dụng', {
            'fields': ('usage_limit', 'used_count', 'valid_from', 'valid_to')
        }),
    )

    def is_expired(self, obj):
        return timezone.now() > obj.valid_to
    is_expired.boolean = True
    is_expired.short_description = 'Hết hạn'
