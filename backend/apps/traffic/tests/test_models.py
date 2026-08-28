"""
Model-level tests for TrafficSignal and SignalPhase — Phase 4C.1.
"""

from django.db import IntegrityError
from django.test import TestCase

from apps.roads.models import Intersection, Road, RoadSegment
from apps.traffic.models import SignalPhase, TrafficSignal


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _intersection(**kw):
    kw.setdefault("name", "Test Junction")
    return Intersection.objects.create(**kw)


def _signal(intersection=None, **kw):
    kw.setdefault("name", "SIG-001")
    return TrafficSignal.objects.create(
        intersection=intersection or _intersection(), **kw
    )


def _phase(signal=None, **kw):
    kw.setdefault("phase_number", 1)
    kw.setdefault("name", "Phase 1")
    kw.setdefault("minimum_green_seconds", 15)
    kw.setdefault("maximum_green_seconds", 60)
    kw.setdefault("yellow_seconds", 4)
    kw.setdefault("all_red_seconds", 2)
    return SignalPhase.objects.create(signal=signal or _signal(), **kw)


# ---------------------------------------------------------------------------
# TrafficSignal model tests
# ---------------------------------------------------------------------------

class TestTrafficSignalModel(TestCase):

    def test_create_minimal(self):
        inter = _intersection(name="Main & Oak")
        sig = TrafficSignal.objects.create(name="SIG-MIN", intersection=inter)
        self.assertEqual(sig.name, "SIG-MIN")
        self.assertEqual(sig.intersection, inter)
        self.assertTrue(sig.is_active)
        self.assertIsNotNone(sig.created_at)
        self.assertIsNotNone(sig.updated_at)

    def test_str_contains_name_and_intersection(self):
        inter = _intersection(name="Oak Ave")
        sig = _signal(intersection=inter, name="SIG-STR")
        self.assertIn("SIG-STR", str(sig))
        self.assertIn("Oak Ave", str(sig))

    def test_name_unique(self):
        _signal(name="SIG-UNIQ")
        with self.assertRaises(IntegrityError):
            _signal(name="SIG-UNIQ")

    def test_is_active_defaults_true(self):
        sig = _signal()
        self.assertTrue(sig.is_active)

    def test_soft_deactivate(self):
        sig = _signal(name="SIG-DEACT")
        sig.is_active = False
        sig.save()
        sig.refresh_from_db()
        self.assertFalse(sig.is_active)

    def test_controller_fields_optional(self):
        inter = _intersection(name="Ctrl Jct")
        sig = TrafficSignal.objects.create(name="SIG-CTRL", intersection=inter)
        self.assertEqual(sig.controller_type, "")
        self.assertEqual(sig.controller_identifier, "")

    def test_controller_fields_stored(self):
        inter = _intersection(name="Ctrl Jct B")
        sig = TrafficSignal.objects.create(
            name="SIG-CTRL2",
            intersection=inter,
            controller_type="Siemens",
            controller_identifier="SN-12345",
        )
        sig.refresh_from_db()
        self.assertEqual(sig.controller_type, "Siemens")
        self.assertEqual(sig.controller_identifier, "SN-12345")

    def test_ordering_by_name(self):
        inter = _intersection(name="Order Jct")
        TrafficSignal.objects.create(name="Z-SIG", intersection=inter)
        TrafficSignal.objects.create(name="A-SIG", intersection=inter)
        names = list(
            TrafficSignal.objects.filter(intersection=inter).values_list("name", flat=True)
        )
        self.assertEqual(names, sorted(names))

    def test_protect_intersection_from_delete(self):
        """Intersection cannot be deleted while a signal references it."""
        from django.db.models.deletion import ProtectedError
        inter = _intersection(name="Protected Jct")
        _signal(intersection=inter)
        with self.assertRaises(ProtectedError):
            inter.delete()

    def test_deactivating_signal_does_not_cascade_phases(self):
        """Deactivating a signal must NOT auto-deactivate its phases."""
        sig = _signal(name="CASCADE-SIG")
        ph = _phase(signal=sig, phase_number=1)
        self.assertTrue(ph.is_active)
        sig.is_active = False
        sig.save()
        ph.refresh_from_db()
        self.assertTrue(ph.is_active)  # phase unchanged


# ---------------------------------------------------------------------------
# SignalPhase model tests
# ---------------------------------------------------------------------------

class TestSignalPhaseModel(TestCase):

    def setUp(self):
        self.signal = _signal(name="PHASE-TEST-SIG")

    def test_create_phase(self):
        ph = _phase(self.signal, phase_number=1)
        self.assertEqual(ph.signal, self.signal)
        self.assertEqual(ph.phase_number, 1)
        self.assertTrue(ph.is_active)

    def test_str_contains_phase_number_and_signal(self):
        ph = _phase(self.signal, phase_number=2, name="North Green")
        s = str(ph)
        self.assertIn("2", s)
        self.assertIn("PHASE-TEST-SIG", s)

    def test_phase_number_unique_within_signal(self):
        _phase(self.signal, phase_number=1)
        with self.assertRaises(IntegrityError):
            _phase(self.signal, phase_number=1)

    def test_phase_number_reuse_across_signals(self):
        sig2 = _signal(name="SIG-OTHER")
        _phase(self.signal, phase_number=1)
        ph2 = _phase(sig2, phase_number=1)  # same number, different signal — allowed
        self.assertEqual(ph2.phase_number, 1)

    def test_timing_fields_stored(self):
        ph = _phase(
            self.signal,
            phase_number=3,
            name="East Green",
            minimum_green_seconds=10,
            maximum_green_seconds=45,
            yellow_seconds=3,
            all_red_seconds=1,
        )
        ph.refresh_from_db()
        self.assertEqual(ph.minimum_green_seconds, 10)
        self.assertEqual(ph.maximum_green_seconds, 45)
        self.assertEqual(ph.yellow_seconds, 3)
        self.assertEqual(ph.all_red_seconds, 1)

    def test_soft_deactivate_phase(self):
        ph = _phase(self.signal, phase_number=1)
        ph.is_active = False
        ph.save()
        ph.refresh_from_db()
        self.assertFalse(ph.is_active)

    def test_protect_signal_from_delete(self):
        """Signal cannot be deleted while phases reference it."""
        from django.db.models.deletion import ProtectedError
        _phase(self.signal, phase_number=1)
        with self.assertRaises(ProtectedError):
            self.signal.delete()

    def test_ordering_by_phase_number(self):
        _phase(self.signal, phase_number=3)
        _phase(self.signal, phase_number=1)
        _phase(self.signal, phase_number=2)
        nums = list(
            SignalPhase.objects.filter(signal=self.signal).values_list("phase_number", flat=True)
        )
        self.assertEqual(nums, [1, 2, 3])

    def test_movement_optional(self):
        ph = _phase(self.signal, phase_number=1)
        self.assertEqual(ph.movement, "")

    def test_timestamps_set(self):
        ph = _phase(self.signal, phase_number=1)
        self.assertIsNotNone(ph.created_at)
        self.assertIsNotNone(ph.updated_at)
