import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from django.test import RequestFactory
from apps.products.supply_permissions import (
    can_view_inventory_check,
    can_view_payment_voucher,
    can_view_bien_do,
    is_warehouse_manager
)

# Get user kho01
user = User.objects.filter(username='kho01').first()

if not user:
    print("✗ User kho01 not found")
    exit(1)

print(f"Testing view access for user: {user.username}")
print(f"  - is_staff: {user.is_staff}")
print(f"  - Groups: {list(user.groups.values_list('name', flat=True))}")
print()

# Create a fake request
factory = RequestFactory()
request = factory.get('/supply/inventory-checks/')
request.user = user

# Test view permissions
print("View access permissions:")
print(f"  - is_warehouse_manager(user): {is_warehouse_manager(user)}")
print(f"  - can_view_inventory_check(request): {can_view_inventory_check(request)}")
print(f"  - can_view_payment_voucher(request): {can_view_payment_voucher(request)}")
print(f"  - can_view_bien_do(request): {can_view_bien_do(request)}")
print()

print("✓ User kho01 should be able to:")
print("  - Access /supply/inventory-checks/ (Phiếu kiểm kê)")
print("  - See 'Phiếu kiểm kê' menu in admin sidebar")
print()

print("✗ User kho01 should NOT be able to:")
print("  - Access /supply/bien-do/ (Biên độ)")
print("  - Access /supply/requests/ (Yêu cầu đặt hàng)")
print("  - Access /supply/payment-vouchers/ (Phiếu chi tiền)")
print("  - See other menu items in 'Chuỗi cung ứng' section")
