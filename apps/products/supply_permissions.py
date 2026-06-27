"""Permission helpers for supply admin sidebar & views."""
from .supply_models import Supplier


def is_store_manager(user):
    if not user.is_authenticated:
        return False
    # Nếu user là Nhà cung cấp thì không phải Cửa hàng trưởng
    if is_supplier_user(user):
        return False
    return (
        user.is_superuser
        or user.is_staff
        or user.has_perm('products.can_approve_purchase')
        or user.has_perm('products.can_receive_goods')
    )


def is_supplier_user(user):
    return user.is_authenticated and Supplier.objects.filter(
        user=user, is_active=True
    ).exists()


def can_view_bien_do(request):
    user = request.user
    return user.is_superuser or is_store_manager(user)


def can_view_bao_gia(request):
    user = request.user
    return user.is_superuser or is_supplier_user(user) or user.is_staff
