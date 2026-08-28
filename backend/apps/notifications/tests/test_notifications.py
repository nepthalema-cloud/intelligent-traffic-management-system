from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.utils import timezone

from apps.accounts.roles import ALL_ROLES
from apps.notifications.models import Notification, NotificationTemplate

User = get_user_model()


class TestNotifications(TestCase):
    def setUp(self):
        for role in ALL_ROLES:
            Group.objects.get_or_create(name=role)

    def test_notification_creation(self):
        user = User.objects.create_user(username="notifyuser", password="Pass123!")
        notification = Notification.objects.create(
            recipient=user,
            notification_type="fine",
            title="Fine issued",
            message="A fine has been generated.",
        )
        self.assertEqual(notification.recipient, user)
        self.assertFalse(notification.is_read)

    def test_template_can_render_body(self):
        template = NotificationTemplate.objects.create(
            code="fine_notice",
            subject="Fine notice for {{ user }}",
            body="Amount: {{ amount }}",
            notification_type="fine",
        )
        rendered = template.render(user="Alice", amount="250.00")
        self.assertIn("Fine notice for Alice", rendered["subject"])
        self.assertIn("Amount: 250.00", rendered["body"])

    def test_mark_as_read(self):
        user = User.objects.create_user(username="readuser", password="Pass123!")
        notification = Notification.objects.create(
            recipient=user,
            notification_type="system",
            title="Alert",
            message="System alert",
        )
        notification.mark_as_read()
        self.assertTrue(notification.is_read)
        self.assertIsNotNone(notification.read_at)
