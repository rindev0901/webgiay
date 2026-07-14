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

    # Không log hành động của khách hàng ẩn danh (trừ tạo đơn)
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
        ip_address=ip,
    )


# ─── Authentication ────────────────────────────────────────────────────────────

@receiver(user_logged_in)
def log_login(sender, request, user, **kwargs):
    create_log(action="Đăng nhập", target=f"Tài khoản: {user.username}", user=user)


@receiver(user_logged_out)
def log_logout(sender, request, user, **kwargs):
    if user:
        create_log(action="Đăng xuất", target=f"Tài khoản: {user.username}", user=user)


# ─── Sản phẩm ──────────────────────────────────────────────────────────────────

@receiver(post_save, sender=Product)
def log_product_save(sender, instance, created, **kwargs):
    # Chỉ log khi có staff thao tác qua request
    user = CurrentRequestMiddleware.get_current_user()
    if not user or not user.is_staff:
        return
    action = "Thêm sản phẩm" if created else "Sửa sản phẩm"
    target = f"Sản phẩm: {instance.name} (ID: {instance.pk})"
    changes = f"Slug: {instance.slug or 'N/A'}"
    create_log(action=action, target=target, changes=changes, user=user)


@receiver(post_delete, sender=Product)
def log_product_delete(sender, instance, **kwargs):
    user = CurrentRequestMiddleware.get_current_user()
    if not user or not user.is_staff:
        return
    target = f"Sản phẩm: {instance.name} (ID: {instance.pk})"
    create_log(action="Xóa sản phẩm", target=target, user=user)


# ─── Đơn hàng ──────────────────────────────────────────────────────────────────

@receiver(post_save, sender=Order)
def log_order_save(sender, instance, created, **kwargs):
    user = CurrentRequestMiddleware.get_current_user()

    if created:
        # Log tạo đơn cho cả khách lẫn staff
        changes = f"Tổng tiền: {int(instance.total_amount):,}₫ | PT thanh toán: {instance.get_payment_method_display()}"
        target = f"Đơn hàng: {instance.code}"
        create_log(action="Tạo đơn hàng", target=target, changes=changes, user=user)
    else:
        # Chỉ log update nếu staff đang thao tác
        if not user or not user.is_staff:
            return
        if instance.order_status == Order.OrderStatus.CANCELLED:
            action = "Hủy đơn hàng"
        else:
            action = "Cập nhật đơn hàng"
        changes = (
            f"Trạng thái đơn: {instance.get_order_status_display()} | "
            f"Thanh toán: {instance.get_payment_status_display()}"
        )
        target = f"Đơn hàng: {instance.code}"
        create_log(action=action, target=target, changes=changes, user=user)


@receiver(post_delete, sender=Order)
def log_order_delete(sender, instance, **kwargs):
    user = CurrentRequestMiddleware.get_current_user()
    if not user or not user.is_staff:
        return
    target = f"Đơn hàng: {instance.code}"
    create_log(action="Xóa đơn hàng", target=target, user=user)


# ─── Người dùng / nhân viên ────────────────────────────────────────────────────

@receiver(post_save, sender=User)
def log_user_save(sender, instance, created, **kwargs):
    actor = CurrentRequestMiddleware.get_current_user()

    if created:
        if instance.is_staff:
            # Admin tạo nhân viên mới
            if not actor or not actor.is_staff:
                return
            action = "Thêm nhân viên"
            changes = f"Tài khoản mới: {instance.username} | Staff: True"
            create_log(action=action, target=f"Tài khoản: {instance.username}", changes=changes, user=actor)
        # Bỏ qua log tự đăng ký của khách hàng
        return

    # Chỉ log update nếu có staff đang thao tác
    if not actor or not actor.is_staff:
        return

    # Không log khi admin tự update chính mình (trừ trường hợp muốn giữ lại thì bỏ dòng này)
    target = f"Tài khoản: {instance.username}"
    if instance.is_staff or instance.is_superuser:
        action = "Sửa thông tin nhân viên"
        changes = f"Email: {instance.email} | Active: {instance.is_active} | Staff: {instance.is_staff} | Superuser: {instance.is_superuser}"
    else:
        action = "Sửa thông tin khách hàng"
        changes = f"Email: {instance.email} | Active: {instance.is_active}"
    create_log(action=action, target=target, changes=changes, user=actor)


@receiver(post_delete, sender=User)
def log_user_delete(sender, instance, **kwargs):
    actor = CurrentRequestMiddleware.get_current_user()
    if not actor or not actor.is_staff:
        return
    create_log(
        action="Xóa tài khoản",
        target=f"Tài khoản: {instance.username}",
        user=actor,
    )
