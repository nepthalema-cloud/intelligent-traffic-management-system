from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.utils import timezone

from apps.accounts.roles import ALL_ROLES
from apps.fines.models import Fine, Payment
from apps.violations.models import Vehicle, TrafficViolation

User = get_user_model()


class TestFineAndPayment(TestCase):
    def setUp(self):
        for role in ALL_ROLES:
            Group.objects.get_or_create(name=role)

    def test_fine_status_flow(self):
        vehicle = Vehicle.objects.create(plate_number="TEST-001", vehicle_type="car")
        violation = TrafficViolation.objects.create(
            violation_type="speeding",
            occurred_at=timezone.now(),
            vehicle=vehicle,
        )
        fine = Fine.objects.create(
            violation=violation,
            amount=250.00,
            status="unpaid",
        )
        self.assertEqual(fine.status, "unpaid")
        fine.transition_to("pending")
        self.assertEqual(fine.status, "pending")
        fine.transition_to("paid")
        self.assertEqual(fine.status, "paid")

    def test_invalid_payment_transition_raises(self):
        vehicle = Vehicle.objects.create(plate_number="TEST-002", vehicle_type="car")
        violation = TrafficViolation.objects.create(
            violation_type="speeding",
            occurred_at=timezone.now(),
            vehicle=vehicle,
        )
        fine = Fine.objects.create(
            violation=violation,
            amount=100.00,
            status="unpaid",
        )
        payment = Payment.objects.create(fine=fine, amount=100.00, status="pending")
        with self.assertRaises(ValueError):
            payment.transition_to("paid")

    def test_payment_reference_unique(self):
        vehicle = Vehicle.objects.create(plate_number="TEST-003", vehicle_type="car")
        violation = TrafficViolation.objects.create(
            violation_type="speeding",
            occurred_at=timezone.now(),
            vehicle=vehicle,
        )
        fine = Fine.objects.create(
            violation=violation,
            amount=50.00,
            status="unpaid",
        )
        Payment.objects.create(fine=fine, amount=50.00, status="pending", payment_reference="PAY-1")
        with self.assertRaises(Exception):
            Payment.objects.create(fine=fine, amount=50.00, status="pending", payment_reference="PAY-1")
