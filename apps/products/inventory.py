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
    Trừ stock cho từng OrderItem theo đúng variant được lưu.
    Dùng select_for_update để tránh race condition.
    Trả về list lỗi (rỗng = thành công).
    """
    errors = []
    items = order.items.select_related('product', 'variant', 'variant__size').all()

    with transaction.atomic():
        for item in items:
            if not item.product:
                continue

            if item.variant:
                # Trừ đúng variant được chọn
                variant = (
                    ProductVariant.objects
                    .select_for_update()
                    .filter(pk=item.variant.pk, is_active=True)
                    .first()
                )
                if not variant:
                    errors.append({'product': item.product_name, 'shortage': item.quantity})
                    continue

                deduct = min(variant.stock, item.quantity)
                _record_movement(
                    variant=variant,
                    movement_type=StockMovement.MovementType.OUT,
                    quantity=-deduct,
                    order_code=order.code,
                    note=f'Bán hàng - đơn {order.code}',
                    actor=actor,
                )
                if deduct < item.quantity:
                    errors.append({
                        'product': item.product_name,
                        'shortage': item.quantity - deduct,
                    })
            else:
                # Fallback cũ: chia đều qua các variant còn hàng
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
                    errors.append({'product': item.product_name, 'shortage': remaining})

    # Ghi ActivityLog cho hành động Trừ tồn kho
    try:
        from apps.accounts.signals import create_log
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user_obj = User.objects.filter(username=actor).first() if actor else None
        
        items_detail = [f"{item.product.name} (x{item.quantity})" for item in items if item.product]
        changes_detail = f"Trừ kho thành công: {', '.join(items_detail)}"
        
        create_log(
            action="Trừ tồn kho",
            target=f"Đơn hàng: {order.code}",
            changes=changes_detail,
            user=user_obj
        )
    except Exception:
        pass

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

    # Ghi ActivityLog cho hành động Cộng tồn kho
    try:
        from apps.accounts.signals import create_log
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user_obj = User.objects.filter(username=actor).first() if actor else None
        
        items_detail = [f"{item.product.name} (x{item.quantity})" for item in items if item.product]
        changes_detail = f"Hoàn kho thành công: {', '.join(items_detail)}"
        
        create_log(
            action="Cộng tồn kho",
            target=f"Đơn hàng: {order.code}",
            changes=changes_detail,
            user=user_obj
        )
    except Exception:
        pass


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
    Kiểm tra từng item trong giỏ theo đúng variant được chọn.
    cart_items: list of dict có key 'product', 'quantity', và tùy chọn 'variant'.
    Trả về list lỗi (rỗng = OK).
    """
    errors = []
    for item in cart_items:
        product  = item.get('product')  if isinstance(item, dict) else getattr(item, 'product', None)
        quantity = item.get('quantity') if isinstance(item, dict) else getattr(item, 'quantity', 0)
        variant  = item.get('variant')  if isinstance(item, dict) else getattr(item, 'variant', None)

        if not product:
            continue

        if variant:
            # Lấy stock mới nhất từ DB (tránh stale data)
            fresh = ProductVariant.objects.filter(pk=variant.pk, is_active=True).first()
            available = fresh.stock if fresh else 0
            label = f'{product.name} (Size {variant.size.name})' if getattr(variant, 'size', None) else product.name
        else:
            # Fallback: tổng stock tất cả variant
            available = sum(
                v.stock for v in
                ProductVariant.objects.filter(product=product, is_active=True)
            )
            label = product.name

        if available < quantity:
            errors.append({
                'product': label,
                'available': available,
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
