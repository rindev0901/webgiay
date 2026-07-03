# Generated migration for inventory check system

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('products', '0005_add_supply_chain'),
    ]

    operations = [
        # Update PurchaseRequest.Status choices
        migrations.AlterField(
            model_name='purchaserequest',
            name='status',
            field=models.CharField(
                choices=[
                    ('draft', 'Bản nháp'),
                    ('sent', 'Đã gửi NCC'),
                    ('quoted', 'NCC đã báo giá'),
                    ('approved', 'Đã duyệt NCC'),
                    ('shipped', 'NCC đã giao hàng'),
                    ('in_checking', 'Đang kiểm kê'),
                    ('checked', 'Đã kiểm kê'),
                    ('received', 'Đã nhận hàng & thanh toán'),
                    ('cancelled', 'Đã hủy')
                ],
                default='draft',
                max_length=20
            ),
        ),

        # Create InventoryCheck model
        migrations.CreateModel(
            name='InventoryCheck',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(blank=True, max_length=20, unique=True, verbose_name='Mã phiếu')),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Chờ kiểm tra'),
                        ('checking', 'Đang kiểm'),
                        ('completed', 'Hoàn thành'),
                        ('approved', 'Đã duyệt'),
                        ('rejected', 'Từ chối')
                    ],
                    default='pending',
                    max_length=20
                )),
                ('checked_at', models.DateTimeField(blank=True, null=True, verbose_name='Thời gian kiểm')),
                ('approved_at', models.DateTimeField(blank=True, null=True, verbose_name='Thời gian duyệt')),
                ('note', models.TextField(blank=True, verbose_name='Ghi chú chung')),
                ('rejection_reason', models.TextField(blank=True, verbose_name='Lý do từ chối')),
                ('total_amount', models.DecimalField(decimal_places=0, default=0, max_digits=15, verbose_name='Tổng tiền thanh toán')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('approved_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='approved_inventory_checks',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Người duyệt'
                )),
                ('checker', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='inventory_checks',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Người kiểm kê'
                )),
                ('purchase_request', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='inventory_check',
                    to='products.purchaserequest',
                    verbose_name='Đợt đặt hàng'
                )),
            ],
            options={
                'verbose_name': 'Phiếu kiểm kê',
                'verbose_name_plural': 'Phiếu kiểm kê',
                'ordering': ['-created_at'],
                'permissions': [
                    ('can_check_inventory', 'Có thể kiểm kê hàng'),
                    ('can_approve_inventory', 'Có thể duyệt phiếu kiểm kê'),
                ],
            },
        ),

        # Create InventoryCheckItem model
        migrations.CreateModel(
            name='InventoryCheckItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ordered_qty', models.PositiveIntegerField(verbose_name='SL đặt hàng')),
                ('received_qty', models.PositiveIntegerField(default=0, verbose_name='SL thực nhận')),
                ('unit_price', models.DecimalField(decimal_places=0, max_digits=12, verbose_name='Đơn giá')),
                ('total_price', models.DecimalField(decimal_places=0, default=0, max_digits=15, verbose_name='Thành tiền')),
                ('is_matched', models.BooleanField(default=True, verbose_name='Khớp đơn hàng')),
                ('note', models.CharField(blank=True, max_length=500, verbose_name='Ghi chú')),
                ('image', models.ImageField(blank=True, null=True, upload_to='inventory_checks/', verbose_name='Ảnh kiểm tra')),
                ('inventory_check', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='items',
                    to='products.inventorycheck',
                    verbose_name='Phiếu kiểm kê'
                )),
                ('variant', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='products.productvariant'
                )),
            ],
            options={
                'verbose_name': 'Chi tiết kiểm kê',
                'verbose_name_plural': 'Chi tiết kiểm kê',
                'unique_together': {('inventory_check', 'variant')},
            },
        ),

        # Create PaymentVoucher model
        migrations.CreateModel(
            name='PaymentVoucher',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(blank=True, max_length=20, unique=True, verbose_name='Mã phiếu chi')),
                ('amount', models.DecimalField(decimal_places=0, max_digits=15, verbose_name='Số tiền')),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Chờ thanh toán'),
                        ('paid', 'Đã thanh toán'),
                        ('cancelled', 'Đã hủy')
                    ],
                    default='pending',
                    max_length=20
                )),
                ('payment_method', models.CharField(blank=True, max_length=100, verbose_name='Phương thức thanh toán')),
                ('payment_ref', models.CharField(blank=True, max_length=200, verbose_name='Mã tham chiếu')),
                ('paid_at', models.DateTimeField(blank=True, null=True, verbose_name='Thời gian thanh toán')),
                ('note', models.TextField(blank=True, verbose_name='Ghi chú')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='created_payment_vouchers',
                    to=settings.AUTH_USER_MODEL
                )),
                ('inventory_check', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='payment_voucher',
                    to='products.inventorycheck',
                    verbose_name='Phiếu kiểm kê'
                )),
                ('paid_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='paid_payment_vouchers',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Người thanh toán'
                )),
                ('supplier', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='products.supplier',
                    verbose_name='Nhà cung cấp'
                )),
            ],
            options={
                'verbose_name': 'Phiếu chi tiền NCC',
                'verbose_name_plural': 'Phiếu chi tiền NCC',
                'ordering': ['-created_at'],
            },
        ),
    ]
