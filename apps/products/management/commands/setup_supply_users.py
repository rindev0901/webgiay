"""
Tạo tài khoản Cửa hàng trưởng + Nhà cung cấp mẫu cho module chuỗi cung ứng.

Cách dùng:
    python manage.py setup_supply_users
    python manage.py setup_supply_users --reset   # đặt lại mật khẩu mặc định
"""
from django.contrib.auth.models import User, Group, Permission
from django.core.management.base import BaseCommand
from apps.products.models import Supplier


STORE_MANAGER = {
    'username': 'cuahangtruong',
    'password': 'ch123456',
    'email': 'cuahangtruong@webgiay.local',
    'first_name': 'Cửa',
    'last_name': 'Hàng Trưởng',
}

SUPPLIERS = [
    {
        'username': 'ncc_puma',
        'password': 'ncc123456',
        'name': 'Puma Việt Nam',
        'contact': 'Nguyễn Văn A',
        'phone': '0901111111',
        'email': 'puma@ncc.local',
    },
    {
        'username': 'ncc_nike',
        'password': 'ncc123456',
        'name': 'Nike Distribution VN',
        'contact': 'Trần Thị B',
        'phone': '0902222222',
        'email': 'nike@ncc.local',
    },
    {
        'username': 'ncc_adidas',
        'password': 'ncc123456',
        'name': 'Adidas Supply Co.',
        'contact': 'Lê Văn C',
        'phone': '0903333333',
        'email': 'adidas@ncc.local',
    },
]


class Command(BaseCommand):
    help = 'Tạo nhóm Cửa hàng trưởng và tài khoản NCC mẫu'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset', action='store_true',
            help='Đặt lại mật khẩu mặc định cho các tài khoản đã tồn tại',
        )

    def handle(self, *args, **options):
        reset = options['reset']

        group, _ = Group.objects.get_or_create(name='Cua hang truong')
        perms = Permission.objects.filter(
            codename__in=['can_approve_purchase', 'can_receive_goods'],
            content_type__app_label='products',
        )
        group.permissions.set(perms)
        self.stdout.write(self.style.SUCCESS(f'[OK] Nhom "{group.name}" - {perms.count()} quyen'))

        sm = self._upsert_user(STORE_MANAGER, reset=reset)
        sm.groups.add(group)
        self.stdout.write(self.style.SUCCESS(
            f'[OK] Cua hang truong: {sm.username} / {STORE_MANAGER["password"]}'
        ))

        for data in SUPPLIERS:
            user = self._upsert_user({
                'username': data['username'],
                'password': data['password'],
                'email': data['email'],
                'first_name': data['name'],
                'last_name': '',
            }, reset=reset)

            supplier, created = Supplier.objects.get_or_create(
                name=data['name'],
                defaults={
                    'contact_name': data['contact'],
                    'phone': data['phone'],
                    'email': data['email'],
                    'user': user,
                    'is_active': True,
                },
            )
            if not created:
                supplier.user = user
                supplier.contact_name = data['contact']
                supplier.phone = data['phone']
                supplier.email = data['email']
                supplier.is_active = True
                supplier.save()

            tag = 'moi' if created else 'cap nhat'
            self.stdout.write(self.style.SUCCESS(
                f'[OK] NCC ({tag}): {data["username"]} / {data["password"]}'
            ))

        self.stdout.write('')
        self.stdout.write('Dang nhap Admin -> /admin/')
        self.stdout.write('  CHT: Sidebar > Biên độ / CHT')
        self.stdout.write('  NCC: Sidebar > Báo giá NCC')

    def _upsert_user(self, data, reset=False):
        user, created = User.objects.get_or_create(
            username=data['username'],
            defaults={
                'email': data.get('email', ''),
                'first_name': data.get('first_name', ''),
                'last_name': data.get('last_name', ''),
            },
        )
        if created or reset:
            user.set_password(data['password'])
            user.is_staff = True
            user.save()
        elif not user.is_staff:
            user.is_staff = True
            user.save(update_fields=['is_staff'])
        return user
