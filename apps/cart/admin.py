from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from django.conf import settings
from unfold.admin import ModelAdmin, TabularInline
from .models import Order, OrderItem, OrderStatusLog, Voucher, CartItem, Cart
from apps.products.inventory import deduct_stock, restore_stock, check_stock
from apps.products.models import StockMovement


# ── Inlines ───────────────────────────────────────────────────
class OrderItemInline(TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = (
        "product_name",
        "product",
        "variant",
        "price",
        "quantity",
        "subtotal_display",
    )
    fields = ("product_name", "variant", "quantity", "price", "subtotal_display")

    def subtotal_display(self, obj):
        v = obj.subtotal or 0
        return f"{int(v):,}₫".replace(",", ".")

    subtotal_display.short_description = "Thành tiền"

    def has_add_permission(self, request, obj=None):
        return False


class OrderStatusLogInline(TabularInline):
    model = OrderStatusLog
    extra = 0
    max_num = 0
    can_delete = False
    readonly_fields = ("created_at", "status", "note", "created_by")
    ordering = ("created_at",)

    def has_add_permission(self, request, obj=None):
        return False


# ── Order Admin ───────────────────────────────────────────────
@admin.register(Order)
class OrderAdmin(ModelAdmin):
    list_display = (
        "code",
        "full_name",
        "payment_status_badge",
        "order_status_badge",
        "payment_method",
        "total_amount_display",
        "delivery_badge",
        "created_at",
    )
    list_filter = (
        "payment_status",
        "order_status",
        "payment_method",
        "delivery_confirmed",
        "created_at",
    )
    search_fields = ("code", "full_name", "phone", "email")
    inlines = [OrderItemInline, OrderStatusLogInline]

    # ── Fields readonly by default ──────────────────────────────
    # order_status  → admin chỉnh (trạng thái đơn hàng)
    # payment_status → admin chỉnh (duyệt TT thủ công, VD: COD, chuyển khoản ngoài)
    # Mọi thứ khác do hệ thống tự điền → readonly
    readonly_fields = (
        # Identity
        "code",
        "created_at",
        "updated_at",
        # Customer info (auto-filled from checkout)
        "user",
        "full_name",
        "phone",
        "email",
        "address",
        # Amounts (calculated at order creation)
        "total_amount",
        "discount_amount",
        "voucher",
        "voucher_code",
        # Payment method — set at checkout, không đổi
        "payment_method",
        # Gateway raw data — hệ thống set, không được sửa
        "momo_trans_id",
        "momo_result_code",
        "momo_message",
        "momo_pay_url",
        "sepay_transaction_id",
        "sepay_status",
        # Delivery — set by customer/shipper via QR
        "delivered_at",
        "delivery_confirmed",
        # Display helpers
        "qr_preview",
    )

    fieldsets = (
        # ── Thông tin đơn hàng ─────────────────────────────────
        (
            "📋 Thông tin đơn hàng",
            {
                "fields": (
                    "code",
                    ("payment_status", "payment_method"),
                    "order_status",  # ← CHỈ field này admin được chỉnh
                    "note",
                    ("created_at", "updated_at"),
                )
            },
        ),
        # ── Khách hàng ─────────────────────────────────────────
        (
            "👤 Khách hàng",
            {"fields": ("user", "full_name", "phone", "email", "address")},
        ),
        # ── Thanh toán ─────────────────────────────────────────
        (
            "💳 Thanh toán",
            {
                "fields": (
                    ("total_amount", "discount_amount"),
                    ("voucher", "voucher_code"),
                    ("momo_trans_id", "momo_result_code"),
                    "momo_message",
                    ("sepay_transaction_id", "sepay_status"),
                ),
                "classes": ("collapse",),
            },
        ),
        # ── Giao hàng ──────────────────────────────────────────
        (
            "🚚 Giao hàng & QR",
            {"fields": ("delivery_confirmed", "delivered_at", "qr_preview")},
        ),
    )

    actions = [
        "action_approve_and_deduct",
        "action_cancel_and_restore",
    ]

    # ── Display helpers ───────────────────────────────────────

    def payment_status_badge(self, obj):
        cfg = {
            "pending": ("#f59e0b", "#fff", "⏳ Chờ TT"),
            "paid": ("#16a34a", "#fff", "✓ Đã TT"),
            "failed": ("#ef4444", "#fff", "✗ Thất bại"),
        }
        bg, fg, label = cfg.get(
            obj.payment_status, ("#ddd", "#333", obj.payment_status)
        )
        return format_html(
            '<span style="background:{};color:{};padding:3px 10px;'
            'border-radius:12px;font-size:11px;font-weight:700;">{}</span>',
            bg,
            fg,
            label,
        )

    payment_status_badge.short_description = "Thanh toán"

    def order_status_badge(self, obj):
        cfg = {
            "new": ("#94a3b8", "#fff", "🆕 Mới"),
            "processing": ("#3b82f6", "#fff", "⚙️ Xử lý"),
            "shipped": ("#8b5cf6", "#fff", "🚚 Đang giao"),
            "delivered": ("#16a34a", "#fff", "✓ Đã giao"),
            "cancelled": ("#9ca3af", "#fff", "✗ Đã hủy"),
        }
        bg, fg, label = cfg.get(obj.order_status, ("#ddd", "#333", obj.order_status))
        return format_html(
            '<span style="background:{};color:{};padding:3px 10px;'
            'border-radius:12px;font-size:11px;font-weight:700;">{}</span>',
            bg,
            fg,
            label,
        )

    order_status_badge.short_description = "Đơn hàng"

    def delivery_badge(self, obj):
        if obj.delivery_confirmed:
            return format_html(
                '<span style="color:#16a34a;font-weight:700;">✓ Đã nhận</span>'
            )
        elif obj.order_status == "shipped":
            return format_html('<span style="color:#8b5cf6;">Đang giao</span>')
        return format_html('<span style="color:#9ca3af;">—</span>')

    delivery_badge.short_description = "Giao hàng"

    def total_amount_display(self, obj):
        return f"{int(obj.total_amount):,}₫".replace(",", ".")

    total_amount_display.short_description = "Tổng tiền"

    def qr_preview(self, obj):
        if not obj.pk:
            return "—"
        base_url = getattr(settings, "SITE_URL", "http://localhost:8000").rstrip("/")
        confirm_url = f"{base_url}/cart/orders/{obj.code}/confirm-delivery/"
        try:
            import qrcode, io, base64

            qr = qrcode.QRCode(version=1, box_size=6, border=2)
            qr.add_data(confirm_url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode()
            return format_html(
                '<img src="data:image/png;base64,{}" style="width:150px;height:150px;" />'
                '<br><small style="color:#888;">Quét để xác nhận giao hàng</small>',
                b64,
            )
        except Exception:
            return format_html(
                '<a href="{}" target="_blank">{}</a>', confirm_url, confirm_url
            )

    qr_preview.short_description = "QR giao hàng"

    # ── Save model: hook vào order_status changes ─────────────

    def _stock_was_deducted(self, order):
        """
        Kiểm tra đơn này đã từng trừ kho hay chưa.
        Dựa vào lịch sử tồn kho loại OUT và mã đơn hàng.
        """
        return StockMovement.objects.filter(
            order_code=order.code,
            movement_type=StockMovement.MovementType.OUT,
        ).exists()

    def _ensure_order_status_log(self, order, status, note, actor):
        """
        Ghi log trạng thái đơn hàng nếu trạng thái đó chưa từng có.
        Tránh bị tạo trùng quá nhiều dòng trong lịch sử đơn hàng.
        """
        if not order.status_logs.filter(status=status).exists():
            order.log_status(
                status,
                note=note,
                actor=actor,
            )

    def save_model(self, request, obj, form, change):
        """
        Lưu đơn hàng trong admin.

        Nguyên tắc mới:
        - Admin sửa trạng thái đơn hàng thì chỉ cập nhật trạng thái và ghi log.
        - Không tự trừ kho khi đổi payment_status.
        - Không tự trừ kho khi đổi order_status.
        - Trừ kho chỉ được thực hiện bằng action: Duyệt đơn + trừ tồn kho.
        """
        actor = str(request.user)
        changed = set(getattr(form, "changed_data", []))

        old_order_status = None

        if change and obj.pk:
            old_order = Order.objects.filter(pk=obj.pk).first()
            if old_order:
                old_order_status = old_order.order_status

        # Đồng bộ field legacy status để các màn hình cũ không bị lệch.
        if "order_status" in changed:
            if obj.order_status == Order.OrderStatus.PROCESSING:
                obj.status = Order.Status.PROCESSING

            elif obj.order_status == Order.OrderStatus.SHIPPED:
                obj.status = Order.Status.SHIPPED

            elif obj.order_status == Order.OrderStatus.DELIVERED:
                obj.status = Order.Status.DELIVERED
                obj.payment_status = Order.PaymentStatus.PAID
                obj.delivery_confirmed = True

                if not obj.delivered_at:
                    obj.delivered_at = timezone.now()

            elif obj.order_status == Order.OrderStatus.CANCELLED:
                obj.status = Order.Status.CANCELLED

        # Lưu trước.
        super().save_model(request, obj, form, change)

        if not change:
            return

        # Ghi lịch sử trạng thái đơn hàng khi admin đổi trạng thái.
        if "order_status" in changed and old_order_status != obj.order_status:
            if obj.order_status == Order.OrderStatus.PROCESSING:
                self._ensure_order_status_log(
                    obj,
                    Order.OrderStatus.PROCESSING,
                    "Đơn hàng đang được xử lý",
                    actor,
                )

            elif obj.order_status == Order.OrderStatus.SHIPPED:
                self._ensure_order_status_log(
                    obj,
                    Order.OrderStatus.PROCESSING,
                    "Đơn hàng đang được xử lý",
                    actor,
                )
                self._ensure_order_status_log(
                    obj,
                    Order.OrderStatus.SHIPPED,
                    "Đơn hàng đang được giao",
                    actor,
                )

            elif obj.order_status == Order.OrderStatus.DELIVERED:
                self._ensure_order_status_log(
                    obj,
                    Order.OrderStatus.PROCESSING,
                    "Đơn hàng đang được xử lý",
                    actor,
                )
                self._ensure_order_status_log(
                    obj,
                    Order.OrderStatus.SHIPPED,
                    "Đơn hàng đang được giao",
                    actor,
                )
                self._ensure_order_status_log(
                    obj,
                    Order.OrderStatus.DELIVERED,
                    "Đã giao hàng thành công",
                    actor,
                )

            elif obj.order_status == Order.OrderStatus.CANCELLED:
                # Chỉ hoàn kho nếu đơn đã từng trừ kho.
                if old_order_status in (
                    Order.OrderStatus.PROCESSING,
                    Order.OrderStatus.SHIPPED,
                ) and self._stock_was_deducted(obj):
                    restore_stock(obj, actor=actor)

                obj.log_status(
                    Order.OrderStatus.CANCELLED,
                    note="Admin hủy đơn hàng",
                    actor=actor,
                )

        # Ghi log thanh toán nếu admin đổi payment_status.
        # Không trừ kho ở đây.
        if "payment_status" in changed:
            obj.log_status(
                obj.payment_status,
                note=f"Admin cập nhật trạng thái thanh toán: {obj.get_payment_status_display()}",
                actor=actor,
            )

    # ── Bulk actions ──────────────────────────────────────────

    @admin.action(description="✅ Duyệt đơn + trừ tồn kho")
    def action_approve_and_deduct(self, request, queryset):
        """
        Admin duyệt đơn và trừ tồn kho thủ công.

        Áp dụng cho mọi phương thức thanh toán:
        - COD
        - SePay
        - MoMo

        Không yêu cầu payment_status phải PAID.
        Không tự động chạy ở payment callback.
        Tránh trừ kho 2 lần bằng cách kiểm tra StockMovement.
        """
        count = 0
        skipped = 0
        already_deducted = 0

        for order in queryset.exclude(
            order_status__in=[
                Order.OrderStatus.DELIVERED,
                Order.OrderStatus.CANCELLED,
            ]
        ):
            # Không trừ kho 2 lần cho cùng một đơn.
            if self._stock_was_deducted(order):
                already_deducted += 1
                continue

            # Kiểm tra tồn kho trước khi trừ.
            stock_errors = check_stock(
                list(
                    order.items.select_related(
                        "product", "variant", "variant__size"
                    ).all()
                )
            )

            if stock_errors:
                err_msg = ", ".join(
                    f"{e['product']} còn {e.get('available', 0)}, cần {e.get('requested', '?')}"
                    for e in stock_errors
                )
                self.message_user(
                    request,
                    f"⚠ Đơn {order.code}: không đủ tồn kho — {err_msg}",
                    level="warning",
                )
                skipped += 1
                continue

            errors = deduct_stock(order, actor=str(request.user))

            if errors:
                err_msg = ", ".join(
                    f"{e['product']} thiếu {e.get('shortage', '?')}" for e in errors
                )
                self.message_user(
                    request,
                    f"⚠ Đơn {order.code}: không đủ tồn kho — {err_msg}",
                    level="warning",
                )
                skipped += 1
                continue

            # Nếu đơn còn NEW thì đưa về Đang xử lý.
            if order.order_status == Order.OrderStatus.NEW:
                order.order_status = Order.OrderStatus.PROCESSING

            # Đồng bộ legacy status.
            if order.payment_status == Order.PaymentStatus.PAID:
                order.status = Order.Status.PAID
            else:
                order.status = Order.Status.PROCESSING

            order.save(update_fields=["order_status", "status", "updated_at"])

            self._ensure_order_status_log(
                order,
                Order.OrderStatus.PROCESSING,
                "Đơn hàng đang được xử lý",
                str(request.user),
            )

            count += 1

        if count:
            self.message_user(request, f"✅ Đã duyệt và trừ tồn kho {count} đơn hàng.")

        if already_deducted:
            self.message_user(
                request,
                f"ℹ {already_deducted} đơn đã từng trừ kho nên không trừ lại.",
                level="warning",
            )

        if skipped:
            self.message_user(
                request,
                f"❌ {skipped} đơn chưa được duyệt do không đủ tồn kho.",
                level="error",
            )

    @admin.action(description="🚚 Chuyển sang Đang giao hàng")
    def action_mark_shipped(self, request, queryset):
        count = 0

        for order in queryset.filter(order_status=Order.OrderStatus.PROCESSING):
            order.order_status = Order.OrderStatus.SHIPPED
            order.status = Order.Status.SHIPPED
            order.save(update_fields=["order_status", "status", "updated_at"])

            self._ensure_order_status_log(
                order,
                Order.OrderStatus.PROCESSING,
                "Đơn hàng đang được xử lý",
                str(request.user),
            )

            self._ensure_order_status_log(
                order,
                Order.OrderStatus.SHIPPED,
                "Đơn hàng đang được giao",
                str(request.user),
            )

            count += 1

        self.message_user(request, f"🚚 Đã cập nhật {count} đơn.")

    @admin.action(description="❌ Hủy đơn + hoàn tồn kho")
    def action_cancel_and_restore(self, request, queryset):
        count = 0
        restored = 0

        for order in queryset.exclude(
            order_status__in=[
                Order.OrderStatus.DELIVERED,
                Order.OrderStatus.CANCELLED,
            ]
        ):
            # Chỉ hoàn kho nếu đơn đã từng trừ kho.
            if self._stock_was_deducted(order):
                restore_stock(order, actor=str(request.user))
                restored += 1

            order.order_status = Order.OrderStatus.CANCELLED
            order.status = Order.Status.CANCELLED
            order.save(update_fields=["order_status", "status", "updated_at"])

            order.log_status(
                Order.OrderStatus.CANCELLED,
                note="Admin hủy đơn hàng",
                actor=str(request.user),
            )

            count += 1

        self.message_user(
            request, f"❌ Đã hủy {count} đơn. Hoàn kho {restored} đơn đã từng trừ kho."
        )


@admin.register(Voucher)
class VoucherAdmin(ModelAdmin):
    list_display = (
        "code",
        "discount_type",
        "discount_value",
        "min_order_amount",
        "used_count",
        "usage_limit",
        "valid_from",
        "valid_to",
        "is_active",
        "is_expired",
    )
    list_filter = ("discount_type", "is_active")
    search_fields = ("code", "description")
    readonly_fields = ("used_count",)
    list_editable = ("is_active",)
    ordering = ("-valid_to",)

    fieldsets = (
        ("Thông tin cơ bản", {"fields": ("code", "description", "is_active")}),
        (
            "Giảm giá",
            {
                "fields": (
                    "discount_type",
                    "discount_value",
                    "min_order_amount",
                    "max_discount_amount",
                )
            },
        ),
        (
            "Giới hạn sử dụng",
            {"fields": ("usage_limit", "used_count", "valid_from", "valid_to")},
        ),
    )

    def is_expired(self, obj):
        return timezone.now() > obj.valid_to

    is_expired.boolean = True
    is_expired.short_description = "Hết hạn"
