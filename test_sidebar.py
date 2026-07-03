import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from django.test import RequestFactory
from config.admin_sidebar import SIDEBAR_NAVIGATION

# Get user kho01
user = User.objects.filter(username='kho01').first()

if not user:
    print("✗ User kho01 not found")
    exit(1)

print(f"Testing sidebar visibility for user: {user.username}")
print(f"  - is_staff: {user.is_staff}")
print(f"  - Groups: {list(user.groups.values_list('name', flat=True))}")
print()

# Create a fake request
factory = RequestFactory()
request = factory.get('/admin/')
request.user = user

# Test each menu item in the "Chuỗi cung ứng" section
supply_section = SIDEBAR_NAVIGATION[0]
print(f"Section: {supply_section['title']}")
print()

for item in supply_section['items']:
    title = item['title']
    has_permission = item.get('permission')

    if has_permission:
        result = has_permission(request)
        print(f"  {'✓' if result else '✗'} {title}: {result}")
    else:
        print(f"  ? {title}: No permission check")

print()
print("Expected behavior:")
print("  - Biên độ / CHT: ✗ (only for store managers)")
print("  - Yêu cầu đặt hàng: ✗ (only for store managers)")
print("  - Phiếu kiểm kê: ✓ (for warehouse managers)")
print("  - Phiếu chi tiền NCC: ✗ (only for store managers)")
print("  - Báo giá NCC: ✗ (only for suppliers)")
