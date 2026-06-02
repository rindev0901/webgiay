"""
inventory.py — Tất cả logic quản lý tồn kho tập trung ở đây.

Các hàm public:
    deduct_stock(order, actor)   — trừ tồn kho khi đơn PAID
    restore_stock(order, actor)  — hoàn tồn kho khi đơn CANCELLED
    adjust_stock(variant, qty, note, actor) — điều chỉnh thủ công
    check_stock(cart_items)      — kiểm tra trước khi checkout
"""
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from django.db import transaction

from .models import ProductVariant, StockMovement

if TYPE_CHECKING:
    from apps.cart.models import Order


# ────────────────────────────────────────────────
# 1. Trừ tồn kho khi đơn hàng được thanh toán
# ────────────────────────────────────────────────
def deduct_stock(order: 'Order', actor: str = 'system') -> list[dict]:
    """
    Trừ stock cho từng OrderItem.
    - Tra variant qua product + SKU stored in order item.
    - Dùng select_for_update để tránh race condition.
    - Trả về list lỗi (rỗng = thành công).
    """
    errors = []
    items = order.items.select_related('product').all()

    with transaction.atomic():
        for item in items:
            if not item.product:
                continue

            # Lấy variant: ưu tiên variant gắn với order item (nếu có)
            # Fallback: lấy variant bất kỳ của product còn stock
            variants = (
                ProductVariant.objects
                .select_for_update()
                .filter(product=item.product, is_active=True)
                .order_by('size__order')
            )

            remaining = item.quantity
            for variant in variants:
                if remaining <= 0:
                    break
                deduct = min(variant.stock, remaining)
                if deduct <= 0:
                    continue

                _record_movement(
                    variant=variant,
                    movement_type=StockMovement.MovementType.OUT,
                    quantity=-deduct,
                    order_code=order.code,
                    note=f'Bán hàng - đơn {order.code}',
                    actor=actor,
                )
                remaining -= deduct

            if remaining > 0:
                errors.append({
                    'product': item.product_name,
                    'shortage': remaining,
                })

    return errors


# ────────────────────────────────────────────────
# 2. Hoàn tồn kho khi đơn bị huỷ
# ────────────────────────────────────────────────
def restore_stock(order: 'Order', actor: str = 'system') -> None:
    """Hoàn lại stock cho từng OrderItem của đơn bị huỷ."""
    items = order.items.select_related('product').all()

    with transaction.atomic():
        for item in items:
            if not item.product:
                continue

            variants = (
                ProductVariant.objects
                .select_for_update()
                .filter(product=item.product, is_active=True)
                .order_by('size__order')
            )

            remaining = item.quantity
            for variant in variants:
                if remaining <= 0:
                    break
                restore = min(item.quantity, remaining)
                _record_movement(
                    variant=variant,
                    movement_type=StockMovement.MovementType.RETURN,
                    quantity=restore,
                    order_code=order.code,
                    note=f'Hoàn hàng - huỷ đơn {order.code}',
                    actor=actor,
                )
                remaining -= restore


# ────────────────────────────────────────────────
# 3. Điều chỉnh tồn kho thủ công (admin)
# ────────────────────────────────────────────────
def adjust_stock(
    variant: ProductVariant,
    quantity: int,          # có thể âm hoặc dương
    note: str = '',
    actor: str = 'admin',
) -> ProductVariant:
    """
    Điều chỉnh tồn kho biến thể.
    quantity > 0: nhập thêm
    quantity < 0: xuất/điều chỉnh giảm
    """
    with transaction.atomic():
        v = ProductVariant.objects.select_for_update().get(pk=variant.pk)
        new_stock = max(0, v.stock + quantity)
        mtype = (
            StockMovement.MovementType.IN if quantity > 0
            else StockMovement.MovementType.ADJUST
        )
        _record_movement(
            variant=v,
            movement_type=mtype,
            quantity=quantity,
            note=note or ('Nhập kho' if quantity > 0 else 'Điều chỉnh'),
            actor=actor,
        )
        v.stock = new_stock
        v.save(update_fields=['stock'])
        return v


# ────────────────────────────────────────────────
# 4. Kiểm tra stock trước khi checkout
# ────────────────────────────────────────────────
def check_stock(cart_items: list) -> list[dict]:
    """
    Kiểm tra xem các sản phẩm trong giỏ còn đủ hàng không.
    cart_items: list of {'product': Product, 'quantity': int}
    Trả về list lỗi (rỗng = OK).
    """
    errors = []
    for item in cart_items:
        product = item.get('product') or getattr(item, 'product', None)
        quantity = item.get('quantity') or getattr(item, 'quantity', 0)
        if not product:
            continue

        total_stock = sum(
            v.stock for v in
            ProductVariant.objects.filter(product=product, is_active=True)
        )
        if total_stock < quantity:
            errors.append({
                'product': product.name,
                'available': total_stock,
                'requested': quantity,
            })
    return errors


# ────────────────────────────────────────────────
# Internal helper
# ────────────────────────────────────────────────
def _record_movement(
    variant: ProductVariant,
    movement_type: str,
    quantity: int,
    order_code: str = '',
    note: str = '',
    actor: str = 'system',
) -> StockMovement:
    """Ghi movement và cập nhật variant.stock trong cùng 1 transaction block."""
    stock_before = variant.stock
    stock_after  = max(0, stock_before + quantity)

    variant.stock = stock_after
    variant.save(update_fields=['stock'])

    return StockMovement.objects.create(
        variant=variant,
        movement_type=movement_type,
        quantity=quantity,
        stock_before=stock_before,
        stock_after=stock_after,
        order_code=order_code,
        note=note,
        created_by=actor,
    )
