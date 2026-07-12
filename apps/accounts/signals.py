from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from apps.products.models import Product
from apps.cart.models import Order
from apps.accounts.models import ActivityLog
from apps.accounts.middleware import CurrentRequestMiddleware

User = get_user_model()

def _get_user_role(user):
    if not user:
        return "Hệ thống"
    if user.is_superuser:
        return "Admin"
    groups = [g.name for g in user.groups.all()]
    if "Tổng Giám Đốc" in groups or "Tổng giám đốc" in groups:
        return "Tổng Giám Đốc"
    if "Giám Đốc" in groups or "Giám đốc" in groups:
        return "Giám Đốc"
    if "Cửa hàng trưởng" in groups or "Cua hang truong" in groups:
        return "Cửa hàng trưởng"
    if "Quản lý kho" in groups or "Quan ly kho" in groups:
        return "Quản lý kho"
    if user.is_staff:
        return "Nhân viên"
    return "Khách hàng"

def create_log(action, target, changes="", user=None):
    if not user:
        user = CurrentRequestMiddleware.get_current_user()
    
    # Don't log anonymous public user actions on products/orders
    if not user and action not in ["Tạo đơn hàng"]:
        return

    username = user.username if user else "system"
    role = _get_user_role(user) if user else "Hệ thống"
    ip = CurrentRequestMiddleware.get_client_ip()

    ActivityLog.objects.create(
        user=user,
        username=username,
        user_role=role,
        action=action,
        target=target,
        changes=changes,
        ip_address=ip
    )

@receiver(user_logged_in)
def log_login(sender, request, user, **kwargs):
    create_log(action="Đăng nhập", target=f"Tài khoản: {user.username}", user=user)

@receiver(user_logged_out)
def log_logout(sender, request, user, **kwargs):
    if user:
        create_log(action="Đăng xuất", target=f"Tài khoản: {user.username}", user=user)

@receiver(post_save, sender=Product)
def log_product_save(sender, instance, created, **kwargs):
    action = "Thêm sản phẩm" if created else "Sửa sản phẩm"
    target = f"Sản phẩm: {instance.name} (ID: {instance.pk})"
    changes = f"Slug: {instance.slug or 'N/A'}"
    create_log(action=action, target=target, changes=changes)

@receiver(post_delete, sender=Product)
def log_product_delete(sender, instance, **kwargs):
    target = f"Sản phẩm: {instance.name} (ID: {instance.pk})"
    create_log(action="Xóa sản phẩm", target=target)

@receiver(post_save, sender=Order)
def log_order_save(sender, instance, created, **kwargs):
    if created:
        action = "Tạo đơn hàng"
        changes = f"Tổng tiền: {int(instance.total_amount):,}₫"
    else:
        if instance.order_status == Order.OrderStatus.CANCELLED:
            action = "Hủy đơn hàng"
        else:
            action = "Cập nhật đơn hàng"
        changes = f"Trạng thái đơn: {instance.get_order_status_display()} | Thanh toán: {instance.get_payment_status_display()}"
    
    target = f"Đơn hàng: {instance.code} (ID: {instance.pk})"
    create_log(action=action, target=target, changes=changes)

@receiver(post_delete, sender=Order)
def log_order_delete(sender, instance, **kwargs):
    target = f"Đơn hàng: {instance.code} (ID: {instance.pk})"
    create_log(action="Xóa dữ liệu (Đơn hàng)", target=target)

@receiver(post_save, sender=User)
def log_user_save(sender, instance, created, **kwargs):
    if created:
        action = "Đăng ký tài khoản" if not instance.is_staff else "Thêm nhân viên"
        target = f"Tài khoản: {instance.username}"
        changes = f"Tạo tài khoản mới cho {instance.get_full_name() or instance.username}"
        create_log(action=action, target=target, changes=changes)
    else:
        target = f"Tài khoản: {instance.username}"
        action = "Cập nhật thông tin khách hàng" if not instance.is_staff else "Thay đổi quyền người dùng / thông tin nhân viên"
        changes = f"Email: {instance.email} | Hoạt động: {instance.is_active} | Staff: {instance.is_staff}"
        create_log(action=action, target=target, changes=changes)

@receiver(post_delete, sender=User)
def log_user_delete(sender, instance, **kwargs):
    target = f"Tài khoản: {instance.username}"
    create_log(action="Xóa dữ liệu (Người dùng)", target=target)
