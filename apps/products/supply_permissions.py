"""Permission helpers for supply admin sidebar & views."""

from django.contrib.auth.models import Group
from .supply_models import Supplier


def is_in_group(user, group_name):
    """Kiểm tra user có thuộc group không."""
    if not user.is_authenticated:
        return False
    return user.groups.filter(name=group_name).exists()


def is_store_manager(user):
    """Kiểm tra user có phải Cửa hàng trưởng không."""
    if not user.is_authenticated:
        return False
    # Nếu user là Nhà cung cấp thì không phải Cửa hàng trưởng
    if is_supplier_user(user):
        return False
    # Kiểm tra theo group hoặc quyền
    return user.is_superuser or (
        is_in_group(user, "Cửa hàng trưởng") or is_in_group(user, "Cua hang truong")
    )


def is_warehouse_manager(user):
    """Kiểm tra user có phải Quản lý kho không (có quyền xem phiếu kiểm kê)."""
    if not user.is_authenticated:
        return False
    return user.is_superuser or (
        user.is_staff
        and (is_in_group(user, "Quản lý kho") or is_in_group(user, "Quan ly kho"))
    )


def is_supplier_user(user):
    """Kiểm tra user có phải Nhà cung cấp không."""
    if not user.is_authenticated:
        return False
    return (
        is_in_group(user, "Nhà cung cấp")
        or is_in_group(user, "Nha cung cap")  # Tên không dấu
        or Supplier.objects.filter(user=user, is_active=True).exists()
    )


def is_inventory_checker(user):
    """Kiểm tra xem user có quyền kiểm kê không."""
    return is_warehouse_manager(user)


def can_view_bien_do(request):
    """Quyền xem biên độ tồn kho."""
    user = request.user
    return user.is_superuser or is_store_manager(user) or is_warehouse_manager(user)


def can_view_bao_gia(request):
    """Quyền xem báo giá."""
    user = request.user
    return user.is_superuser or is_supplier_user(user) or user.is_staff


def can_view_inventory_check(request):
    """Quyền xem phiếu kiểm kê - Quản lý kho và Admin."""
    user = request.user
    return user.is_superuser or is_warehouse_manager(user)


def can_view_payment_voucher(request):
    """Quyền xem phiếu chi tiền - Cửa hàng trưởng và Admin."""
    user = request.user
    return user.is_superuser or is_store_manager(user)


def is_director_or_general_director(user):
    """Check if user is a director or general director or superuser."""
    if not user.is_authenticated:
        return False
    return user.is_superuser or any(
        is_in_group(user, g) for g in ["Giám đốc", "Giám Đốc", "Tổng giám đốc", "Tổng Giám Đốc"]
    )
