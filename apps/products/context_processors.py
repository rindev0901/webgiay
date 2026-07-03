"""Context processors for products app"""
from .models import Category, Brand
from .supply_permissions import is_store_manager, is_supplier_user, is_warehouse_manager
from .supply_admin_paths import SUPPLY_PATHS


def navigation_data(request):
    """Categories & brands for public site navigation."""
    return {
        'categories': Category.objects.filter(is_active=True).order_by('name'),
        'brands': Brand.objects.filter(is_active=True).order_by('name'),
    }


def supply_nav(request):
    user = request.user
    supplier = None
    if user.is_authenticated:
        from .supply_models import Supplier
        supplier = Supplier.objects.filter(user=user, is_active=True).first()
    return {
        'supply_is_manager': is_store_manager(user),
        'supply_is_supplier': is_supplier_user(user),
        'supply_is_warehouse_manager': is_warehouse_manager(user),
        'supply_paths': SUPPLY_PATHS,
        'supply_supplier': supplier,
    }
