# Vehicle model tests - Phase 4D.1
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.violations.models import Vehicle


def _vehicle(**kw):
    kw.setdefault("plate_number", "ABC-123")
    kw.setdefault("vehicle_type", "car")
    return Vehicle.objects.create(**kw)


class TestVehicleModel(TestCase):
    def test_create_minimal(self):
        v = _vehicle()
        self.assertIsNotNone(v.pk)
        self.assertTrue(v.is_active)
        self.assertIsNotNone(v.created_at)
        self.assertIsNotNone(v.updated_at)

    def test_default_is_active_true(self):
        v = _vehicle(plate_number="DEF-456")
        self.assertTrue(v.is_active)

    def test_default_vehicle_type_other(self):
        v = Vehicle.objects.create(plate_number="GHI-789", vehicle_type="other")
        self.assertEqual(v.vehicle_type, "other")

    def test_all_vehicle_types_valid(self):
        for i, (choice, _) in enumerate(Vehicle.VehicleType.choices):
            v = Vehicle.objects.create(
                plate_number=f"TYPE-{i:03d}", vehicle_type=choice
            )
            self.assertEqual(v.vehicle_type, choice)

    def test_optional_fields_default_empty(self):
        v = _vehicle(plate_number="OPT-111")
        self.assertEqual(v.registration_country, "")
        self.assertEqual(v.color, "")
        self.assertEqual(v.make, "")
        self.assertEqual(v.model, "")
        self.assertIsNone(v.year)

    def test_all_fields_stored(self):
        v = Vehicle.objects.create(
            plate_number="FULL-001",
            vehicle_type="car",
            registration_country="US",
            color="Red",
            make="Toyota",
            model="Camry",
            year=2020,
        )
        v.refresh_from_db()
        self.assertEqual(v.registration_country, "US")
        self.assertEqual(v.color, "Red")
        self.assertEqual(v.make, "Toyota")
        self.assertEqual(v.model, "Camry")
        self.assertEqual(v.year, 2020)

    def test_str_contains_plate_and_type(self):
        v = _vehicle(plate_number="STR-001", vehicle_type="truck")
        self.assertIn("STR-001", str(v))
        self.assertIn("truck", str(v))

    def test_soft_deactivate(self):
        v = _vehicle(plate_number="DEACT-001")
        v.is_active = False; v.save()
        v.refresh_from_db()
        self.assertFalse(v.is_active)

    def test_no_unique_constraint_on_plate_number(self):
        """Architecture does not specify uniqueness — duplicates allowed."""
        Vehicle.objects.create(plate_number="SAME-001", vehicle_type="car")
        Vehicle.objects.create(plate_number="SAME-001", vehicle_type="truck")
        count = Vehicle.objects.filter(plate_number="SAME-001").count()
        self.assertEqual(count, 2)

    def test_year_too_old_fails_validation(self):
        v = Vehicle(plate_number="OLD-001", vehicle_type="car", year=1800)
        with self.assertRaises(ValidationError):
            v.full_clean()

    def test_year_far_future_fails_validation(self):
        v = Vehicle(plate_number="FUT-001", vehicle_type="car", year=2200)
        with self.assertRaises(ValidationError):
            v.full_clean()

    def test_year_valid_current_year(self):
        current = timezone.now().year
        v = Vehicle(plate_number="NOW-001", vehicle_type="car", year=current)
        v.full_clean()  # must not raise

    def test_ordering_newest_first(self):
        v1 = _vehicle(plate_number="ORD-001")
        v2 = _vehicle(plate_number="ORD-002")
        pks = list(
            Vehicle.objects.filter(pk__in=[v1.pk, v2.pk]).values_list("pk", flat=True)
        )
        self.assertEqual(pks[0], v2.pk)
