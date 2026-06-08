from django.contrib import admin
from django.utils import timezone
from unfold.admin import ModelAdmin, TabularInline

from .models import Order, OrderItem, Voucher, CartItem, Cart


class OrderItemInline(TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product_name', 'product', 'variant', 'price', 'quantity', 'subtotal')
    fields = ('product_name', 'variant', 'quantity', 'price', 'subtotal')

    def subtotal(self, obj):
        return obj.subtotal
    subtotal.short_description = 'Thành tiền'


@admin.register(Order)
class OrderAdmin(ModelAdmin):
    list_display  = ('code', 'user', 'status', 'payment_method',
                     'total_amount', 'discount_amount', 'voucher_code', 'created_at')
    list_filter   = ('status', 'payment_method', 'created_at')
    search_fields = ('code', 'full_name', 'phone', 'email', 'voucher_code')
    inlines = [OrderItemInline]
    readonly_fields = ('code', 'created_at', 'updated_at')


@admin.register(OrderItem)
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
