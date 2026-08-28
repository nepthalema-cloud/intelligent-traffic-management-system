from django.conf import settings
from django.db import models


class NotificationTemplate(models.Model):
    """Reusable notification template for backend-generated in-app notifications."""

    code = models.CharField(max_length=120, unique=True, db_index=True)
    notification_type = models.CharField(
        max_length=40,
        choices=[
            ("system", "System"),
            ("traffic", "Traffic"),
            ("camera", "Camera"),
            ("violation", "Violation"),
            ("fine", "Fine"),
            ("payment", "Payment"),
            ("admin", "Admin"),
        ],
        default="system",
        db_index=True,
    )
    subject = models.CharField(max_length=200)
    body = models.TextField()
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "notifications"
        verbose_name = "Notification Template"
        verbose_name_plural = "Notification Templates"
        ordering = ["code"]

    def render(self, **context):
        from django.template import Template, Context

        subject = Template(self.subject).render(Context(context))
        body = Template(self.body).render(Context(context))
        return {"subject": subject, "body": body}

    def __str__(self) -> str:
        return self.code


class Notification(models.Model):
    """In-app notification message associated with a user and optional related object."""

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    notification_type = models.CharField(
        max_length=40,
        choices=[
            ("system", "System"),
            ("traffic", "Traffic"),
            ("camera", "Camera"),
            ("violation", "Violation"),
            ("fine", "Fine"),
            ("payment", "Payment"),
            ("admin", "Admin"),
        ],
        default="system",
        db_index=True,
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    related_model = models.CharField(max_length=100, blank=True, default="")
    related_id = models.PositiveIntegerField(null=True, blank=True)
    is_read = models.BooleanField(default=False, db_index=True)
    delivery_status = models.CharField(
        max_length=20,
        choices=[
            ("queued", "Queued"),
            ("sent", "Sent"),
            ("failed", "Failed"),
        ],
        default="queued",
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "notifications"
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read"], name="notif_recipient_unread_idx"),
        ]

    def mark_as_read(self):
        self.is_read = True
        from django.utils import timezone

        self.read_at = timezone.now()
        self.save(update_fields=["is_read", "read_at"])

    def __str__(self) -> str:
        return f"{self.recipient} - {self.title}"
