from django.db import models
from django.conf import settings

class ActivityLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs",
        verbose_name="Nhân viên"
    )
    username = models.CharField(max_length=150, verbose_name="Tên tài khoản")
    user_role = models.CharField(max_length=100, blank=True, verbose_name="Chức vụ")
    action = models.CharField(max_length=100, verbose_name="Hành động")
    target = models.CharField(max_length=255, blank=True, verbose_name="Đối tượng tác động")
    changes = models.TextField(blank=True, verbose_name="Nội dung thay đổi")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="Địa chỉ IP")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Thời gian")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Lịch sử hoạt động"
        verbose_name_plural = "Lịch sử hoạt động"

    def __str__(self):
        return f"{self.username} - {self.action} - {self.created_at}"
