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
    can_delete = False
    readonly_fields = ('product_name', 'product', 'variant', 'price', 'quantity', 'subtotal_display')
    fields = ('product_name', 'variant', 'quantity', 'price', 'subtotal_display')

    def subtotal_display(self, obj):
        v = obj.subtotal or 0
        return f"{int(v):,}₫".replace(',', '.')
    subtotal_display.short_description = 'Thành tiền'

    def has_add_permission(self, request, obj=None):
        return False


class OrderStatusLogInline(TabularInline):
    model = OrderStatusLog
    extra = 0
    max_num = 0
    can_delete = False
    readonly_fields = ('created_at', 'status', 'note', 'created_by')
    ordering = ('created_at',)

    def has_add_permission(self, request, obj=None):
        return False


# ── Order Admin ───────────────────────────────────────────────
@admin.register(Order)
class OrderAdmin(ModelAdmin):
    list_display = (
        'code', 'full_name', 'payment_status_badge', 'order_status_badge',
        'payment_method', 'total_amount_display', 'delivery_badge', 'created_at',
    )
    list_filter  = ('payment_status', 'order_status', 'payment_method', 'delivery_confirmed', 'created_at')
    search_fields = ('code', 'full_name', 'phone', 'email')
    inlines = [OrderItemInline, OrderStatusLogInline]

    # ── Fields readonly by default ──────────────────────────────
    # order_status  → admin chỉnh (trạng thái đơn hàng)
    # payment_status → admin chỉnh (duyệt TT thủ công, VD: COD, chuyển khoản ngoài)
    # Mọi thứ khác do hệ thống tự điền → readonly
    readonly_fields = (
        # Identity
        'code', 'created_at', 'updated_at',
        # Customer info (auto-filled from checkout)
        'user', 'full_name', 'phone', 'email', 'address',
        # Amounts (calculated at order creation)
        'total_amount', 'discount_amount', 'voucher', 'voucher_code',
        # Payment method — set at checkout, không đổi
        'payment_method',
        # Gateway raw data — hệ thống set, không được sửa
        'momo_trans_id', 'momo_result_code', 'momo_message', 'momo_pay_url',
        'sepay_transaction_id', 'sepay_status',
        # Delivery — set by customer/shipper via QR
        'delivered_at', 'delivery_confirmed',
        # Display helpers
        'qr_preview',
    )

    fieldsets = (
        # ── Thông tin đơn hàng ─────────────────────────────────
        ('📋 Thông tin đơn hàng', {
            'fields': (
                'code',
                ('payment_status', 'payment_method'),
                'order_status',          # ← CHỈ field này admin được chỉnh
                'note',
                ('created_at', 'updated_at'),
            )
        }),
        # ── Khách hàng ─────────────────────────────────────────
        ('👤 Khách hàng', {
            'fields': ('user', 'full_name', 'phone', 'email', 'address')
        }),
        # ── Thanh toán ─────────────────────────────────────────
        ('💳 Thanh toán', {
            'fields': (
                ('total_amount', 'discount_amount'),
                ('voucher', 'voucher_code'),
                ('momo_trans_id', 'momo_result_code'),
                'momo_message',
                ('sepay_transaction_id', 'sepay_status'),
            ),
            'classes': ('collapse',),
        }),
        # ── Giao hàng ──────────────────────────────────────────
        ('🚚 Giao hàng & QR', {
            'fields': ('delivery_confirmed', 'delivered_at', 'qr_preview')
        }),
    )

    actions = [
        'action_approve_and_deduct',
        'action_mark_shipped',
        'action_cancel_and_restore',
    ]

    # ── Display helpers ───────────────────────────────────────

    def payment_status_badge(self, obj):
        cfg = {
            'pending': ('#f59e0b', '#fff', '⏳ Chờ TT'),
            'paid':    ('#16a34a', '#fff', '✓ Đã TT'),
            'failed':  ('#ef4444', '#fff', '✗ Thất bại'),
        }
        bg, fg, label = cfg.get(obj.payment_status, ('#ddd', '#333', obj.payment_status))
        return format_html(
            '<span style="background:{};color:{};padding:3px 10px;'
            'border-radius:12px;font-size:11px;font-weight:700;">{}</span>',
            bg, fg, label
        )
    payment_status_badge.short_description = 'Thanh toán'

    def order_status_badge(self, obj):
        cfg = {
            'new':        ('#94a3b8', '#fff', '🆕 Mới'),
            'processing': ('#3b82f6', '#fff', '⚙️ Xử lý'),
            'shipped':    ('#8b5cf6', '#fff', '🚚 Đang giao'),
            'delivered':  ('#16a34a', '#fff', '✓ Đã giao'),
            'cancelled':  ('#9ca3af', '#fff', '✗ Đã hủy'),
        }
        bg, fg, label = cfg.get(obj.order_status, ('#ddd', '#333', obj.order_status))
        return format_html(
            '<span style="background:{};color:{};padding:3px 10px;'
            'border-radius:12px;font-size:11px;font-weight:700;">{}</span>',
            bg, fg, label
        )
    order_status_badge.short_description = 'Đơn hàng'

    def delivery_badge(self, obj):
        if obj.delivery_confirmed:
            return format_html('<span style="color:#16a34a;font-weight:700;">✓ Đã nhận</span>')
        elif obj.order_status == 'shipped':
            return format_html('<span style="color:#8b5cf6;">Đang giao</span>')
        return format_html('<span style="color:#9ca3af;">—</span>')
    delivery_badge.short_description = 'Giao hàng'

    def total_amount_display(self, obj):
        return f"{int(obj.total_amount):,}₫".replace(',', '.')
    total_amount_display.short_description = 'Tổng tiền'

    def qr_preview(self, obj):
        if not obj.pk:
            return '—'
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

    # ── Save model: hook vào order_status changes ─────────────

    def save_model(self, request, obj, form, change):
        if change:
            old = Order.objects.get(pk=obj.pk)
            changed = form.changed_data

            # ── 1. payment_status thay đổi ─────────────────────
            if 'payment_status' in changed:
                new_ps = obj.payment_status

                # Admin đánh dấu PAID thủ công (VD: COD đã nhận tiền, CK ngoài)
                if (
                    old.payment_status != Order.PaymentStatus.PAID
                    and new_ps == Order.PaymentStatus.PAID
                ):
                    super().save_model(request, obj, form, change)
                    # Nếu đơn đang NEW → tự động chuyển sang PROCESSING và trừ kho
                    if obj.order_status == Order.OrderStatus.NEW:
                        from apps.products.inventory import deduct_stock as _deduct
                        errors = _deduct(obj, actor=str(request.user))
                        if errors:
                            err_msg = ', '.join(
                                f"{e['product']} (thiếu {e.get('shortage', '?')})" for e in errors
                            )
                            self.message_user(
                                request,
                                f'⚠ Đơn {obj.code}: không đủ tồn kho — {err_msg}',
                                level='warning',
                            )
                        else:
                            obj.order_status = Order.OrderStatus.PROCESSING
                            obj.save(update_fields=['order_status', 'updated_at'])
                        obj.log_status(
                            'paid',
                            note='Admin xác nhận đã thanh toán (thủ công)',
                            actor=str(request.user)
                        )
                    return

                # Admin đặt FAILED/PENDING thủ công
                obj.log_status(
                    new_ps,
                    note=f'Admin cập nhật trạng thái thanh toán: {obj.get_payment_status_display()}',
                    actor=str(request.user)
                )

            # ── 2. order_status thay đổi ────────────────────────
            if 'order_status' in changed:
                new_os = obj.order_status

                # Duyệt đơn: PAID + NEW → PROCESSING → trừ kho
                if (
                    old.payment_status == Order.PaymentStatus.PAID
                    and old.order_status == Order.OrderStatus.NEW
                    and new_os == Order.OrderStatus.PROCESSING
                ):
                    super().save_model(request, obj, form, change)
                    errors = deduct_stock(obj, actor=str(request.user))
                    if errors:
                        err_msg = ', '.join(
                            f"{e['product']} (thiếu {e.get('shortage', '?')})" for e in errors
                        )
                        self.message_user(
                            request,
                            f'⚠ Đơn {obj.code}: không đủ tồn kho — {err_msg}',
                            level='warning',
                        )
                    obj.log_status(
                        'processing',
                        note='Admin duyệt đơn, đã trừ tồn kho',
                        actor=str(request.user)
                    )
                    return

                # Hủy đơn đã xử lý → hoàn kho
                if (
                    new_os == Order.OrderStatus.CANCELLED
                    and old.order_status in (Order.OrderStatus.PROCESSING, Order.OrderStatus.SHIPPED)
                ):
                    super().save_model(request, obj, form, change)
                    restore_stock(obj, actor=str(request.user))
                    obj.log_status(
                        'cancelled',
                        note='Admin hủy đơn, đã hoàn tồn kho',
                        actor=str(request.user)
                    )
                    return

                # Các thay đổi khác
                obj.log_status(new_os, note='Admin cập nhật trạng thái đơn hàng', actor=str(request.user))

        super().save_model(request, obj, form, change)

    # ── Bulk actions ──────────────────────────────────────────

    @admin.action(description='✅ Duyệt đơn + trừ tồn kho (PAID → PROCESSING)')
    def action_approve_and_deduct(self, request, queryset):
        """Duyệt các đơn đã thanh toán (payment_status=PAID, order_status=NEW)."""
        count = skipped = 0
        qs = queryset.filter(
            payment_status=Order.PaymentStatus.PAID,
            order_status=Order.OrderStatus.NEW,
        )
        for order in qs:
            errors = deduct_stock(order, actor=str(request.user))
            if errors:
                err_msg = ', '.join(
                    f"{e['product']} (thiếu {e.get('shortage', '?')})" for e in errors
                )
                self.message_user(request, f'⚠ Đơn {order.code}: {err_msg}', level='warning')
                skipped += 1
                continue
            order.order_status = Order.OrderStatus.PROCESSING
            order.save(update_fields=['order_status', 'updated_at'])
            order.log_status('processing', note='Admin duyệt đơn, đã trừ tồn kho', actor=str(request.user))
            count += 1

        if count:
            self.message_user(request, f'✅ Đã duyệt {count} đơn hàng.')
        if skipped:
            self.message_user(request, f'❌ {skipped} đơn không đủ tồn kho.', level='error')

    # @admin.action(description='🚚 Chuyển sang Đang giao hàng')
    # def action_mark_shipped(self, request, queryset):
    #     count = 0
    #     for order in queryset.filter(order_status=Order.OrderStatus.PROCESSING):
    #         order.order_status = Order.OrderStatus.SHIPPED
    #         order.save(update_fields=['order_status', 'updated_at'])
    #         order.log_status('shipped', note='Đã bàn giao shipper', actor=str(request.user))
    #         count += 1
    #     self.message_user(request, f'🚚 Đã cập nhật {count} đơn.')

    @admin.action(description='❌ Hủy đơn + hoàn tồn kho')
    def action_cancel_and_restore(self, request, queryset):
        count = 0
        for order in queryset.exclude(
            order_status__in=[Order.OrderStatus.DELIVERED, Order.OrderStatus.CANCELLED]
        ):
            if order.order_status in (Order.OrderStatus.PROCESSING, Order.OrderStatus.SHIPPED):
                restore_stock(order, actor=str(request.user))
            order.order_status = Order.OrderStatus.CANCELLED
            order.save(update_fields=['order_status', 'updated_at'])
            order.log_status('cancelled', note='Admin hủy đơn', actor=str(request.user))
            count += 1
        self.message_user(request, f'❌ Đã hủy {count} đơn.')


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
