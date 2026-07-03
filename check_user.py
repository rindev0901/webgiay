import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from apps.products.supply_permissions import is_warehouse_manager, is_store_manager, is_in_group

# Check user kho01
username = 'kho01'
user = User.objects.filter(username=username).first()

if user:
    print(f"✓ User found: {username}")
    print(f"  - is_staff: {user.is_staff}")
    print(f"  - is_superuser: {user.is_superuser}")
    print(f"  - is_active: {user.is_active}")
    groups = list(user.groups.values_list('name', flat=True))
    print(f"  - Groups: {groups}")
    print()

    # Check permissions
    print("Permission checks:")
    print(f"  - is_warehouse_manager: {is_warehouse_manager(user)}")
    print(f"  - is_store_manager: {is_store_manager(user)}")
    print(f"  - is_in_group('Quản lý kho'): {is_in_group(user, 'Quản lý kho')}")
    print(f"  - is_in_group('Quan ly kho'): {is_in_group(user, 'Quan ly kho')}")
else:
    print(f"✗ User '{username}' not found")

# List all groups
print("\nAll groups in database:")
from django.contrib.auth.models import Group
for group in Group.objects.all():
    print(f"  - '{group.name}'")
