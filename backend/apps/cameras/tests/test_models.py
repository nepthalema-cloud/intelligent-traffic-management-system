"""
Model-level tests for Camera, CameraHealth, Sensor, SensorHealth.
"""

from django.db import IntegrityError
from django.test import TestCase

from apps.cameras.models import (
    Camera, CameraHealth, ConnectivityStatus, HealthStatus, Sensor, SensorHealth,
)
from apps.roads.models import Intersection, Road, RoadSegment


def _road(**kw):
    kw.setdefault("name", "Test Road")
    return Road.objects.create(**kw)


def _segment(**kw):
    road = kw.pop("road", None) or _road()
    kw.setdefault("lane_count", 2)
    return RoadSegment.objects.create(road=road, **kw)


def _intersection(**kw):
    kw.setdefault("name", "Test Intersection")
    return Intersection.objects.create(**kw)


def _camera(**kw):
    kw.setdefault("name", "CAM-001")
    return Camera.objects.create(**kw)


def _sensor(**kw):
    kw.setdefault("name", "SEN-001")
    return Sensor.objects.create(**kw)


class TestCameraModel(TestCase):
    def test_create_camera_minimal(self):
        cam = _camera(name="CAM-MIN")
        self.assertEqual(cam.name, "CAM-MIN")
        self.assertTrue(cam.is_active)
        self.assertIsNone(cam.segment)
        self.assertIsNone(cam.intersection)

    def test_camera_str(self):
        cam = _camera(name="CAM-STR", camera_type="ptz")
        self.assertIn("CAM-STR", str(cam))
        self.assertIn("ptz", str(cam))

    def test_camera_name_unique(self):
        _camera(name="CAM-UNIQ")
        with self.assertRaises(IntegrityError):
            _camera(name="CAM-UNIQ")

    def test_camera_with_segment(self):
        seg = _segment()
        cam = _camera(name="CAM-SEG", segment=seg)
        self.assertEqual(cam.segment, seg)

    def test_camera_with_intersection(self):
        inter = _intersection(name="Jct-A")
        cam = _camera(name="CAM-INT", intersection=inter)
        self.assertEqual(cam.intersection, inter)

    def test_camera_segment_set_null_on_segment_delete(self):
        """SET_NULL: deleting a segment nullifies camera.segment."""
        road = _road(name="Null Road")
        seg = _segment(road=road)
        cam = _camera(name="CAM-NULL", segment=seg)
        # Force-delete the segment (bypass PROTECT by also clearing lanes)
        seg.is_active = False; seg.save()
        # Direct DB delete to test SET_NULL
        RoadSegment.objects.filter(pk=seg.pk).delete()
        cam.refresh_from_db()
        self.assertIsNone(cam.segment)

    def test_camera_types_all_valid(self):
        for i, (choice, _) in enumerate(Camera.CameraType.choices):
            cam = Camera.objects.create(name=f"CAM-TYPE-{i}", camera_type=choice)
            self.assertEqual(cam.camera_type, choice)

    def test_camera_ordering(self):
        Camera.objects.create(name="Z-CAM")
        Camera.objects.create(name="A-CAM")
        names = list(Camera.objects.values_list("name", flat=True))
        self.assertEqual(names, sorted(names))


class TestCameraHealthModel(TestCase):
    def setUp(self):
        self.cam = _camera(name="HEALTH-CAM")

    def test_create_health(self):
        h = CameraHealth.objects.create(
            camera=self.cam,
            health_status=HealthStatus.HEALTHY,
            connectivity_status=ConnectivityStatus.CONNECTED,
        )
        self.assertEqual(h.health_status, HealthStatus.HEALTHY)
        self.assertEqual(h.connectivity_status, ConnectivityStatus.CONNECTED)

    def test_health_one_to_one_enforced(self):
        CameraHealth.objects.create(camera=self.cam)
        with self.assertRaises(IntegrityError):
            CameraHealth.objects.create(camera=self.cam)

    def test_health_default_unknown(self):
        h = CameraHealth.objects.create(camera=self.cam)
        self.assertEqual(h.health_status, HealthStatus.UNKNOWN)
        self.assertEqual(h.connectivity_status, ConnectivityStatus.UNKNOWN)

    def test_health_str(self):
        h = CameraHealth.objects.create(
            camera=self.cam,
            health_status="healthy",
            connectivity_status="connected",
        )
        self.assertIn("HEALTH-CAM", str(h))

    def test_health_cascades_on_camera_delete(self):
        CameraHealth.objects.create(camera=self.cam)
        pk = self.cam.pk
        Camera.objects.filter(pk=pk).delete()
        self.assertFalse(CameraHealth.objects.filter(camera_id=pk).exists())

    def test_replace_latest_upsert_semantics(self):
        """Calling upsert twice updates in-place, not inserts a new row."""
        from apps.cameras.services import CameraService
        CameraService.upsert_health(self.cam, "healthy", "connected")
        CameraService.upsert_health(self.cam, "degraded", "disconnected")
        self.assertEqual(CameraHealth.objects.filter(camera=self.cam).count(), 1)
        h = CameraHealth.objects.get(camera=self.cam)
        self.assertEqual(h.health_status, "degraded")


class TestSensorModel(TestCase):
    def test_create_sensor_minimal(self):
        sen = _sensor(name="SEN-MIN")
        self.assertEqual(sen.name, "SEN-MIN")
        self.assertTrue(sen.is_active)

    def test_sensor_str(self):
        sen = _sensor(name="SEN-STR", sensor_type="radar")
        self.assertIn("SEN-STR", str(sen))
        self.assertIn("radar", str(sen))

    def test_sensor_name_unique(self):
        _sensor(name="SEN-UNIQ")
        with self.assertRaises(IntegrityError):
            _sensor(name="SEN-UNIQ")

    def test_sensor_with_segment(self):
        road = _road(name="Sensor Road")
        seg = _segment(road=road)
        sen = _sensor(name="SEN-SEG", segment=seg)
        self.assertEqual(sen.segment, seg)

    def test_sensor_types_all_valid(self):
        for i, (choice, _) in enumerate(Sensor.SensorType.choices):
            sen = Sensor.objects.create(name=f"SEN-TYPE-{i}", sensor_type=choice)
            self.assertEqual(sen.sensor_type, choice)


class TestSensorHealthModel(TestCase):
    def setUp(self):
        self.sen = _sensor(name="HEALTH-SEN")

    def test_create_sensor_health(self):
        h = SensorHealth.objects.create(
            sensor=self.sen,
            health_status=HealthStatus.HEALTHY,
            connectivity_status=ConnectivityStatus.CONNECTED,
        )
        self.assertEqual(h.health_status, HealthStatus.HEALTHY)

    def test_sensor_health_one_to_one_enforced(self):
        SensorHealth.objects.create(sensor=self.sen)
        with self.assertRaises(IntegrityError):
            SensorHealth.objects.create(sensor=self.sen)

    def test_sensor_health_replace_latest(self):
        from apps.cameras.services import SensorService
        SensorService.upsert_health(self.sen, "healthy", "connected")
        SensorService.upsert_health(self.sen, "offline", "disconnected")
        self.assertEqual(SensorHealth.objects.filter(sensor=self.sen).count(), 1)
        h = SensorHealth.objects.get(sensor=self.sen)
        self.assertEqual(h.health_status, "offline")

    def test_sensor_health_cascades_on_sensor_delete(self):
        SensorHealth.objects.create(sensor=self.sen)
        pk = self.sen.pk
        Sensor.objects.filter(pk=pk).delete()
        self.assertFalse(SensorHealth.objects.filter(sensor_id=pk).exists())
