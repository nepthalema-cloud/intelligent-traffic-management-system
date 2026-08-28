"""
Model-level tests for Road, Intersection, RoadSegment, Lane.
"""

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from apps.roads.models import Intersection, Lane, Road, RoadSegment


def _road(**kw):
    kw.setdefault("name", "Test Road")
    kw.setdefault("road_type", Road.RoadType.PRIMARY)
    return Road.objects.create(**kw)


def _intersection(**kw):
    kw.setdefault("name", "Test Intersection")
    return Intersection.objects.create(**kw)


def _segment(road=None, **kw):
    road = road or _road()
    kw.setdefault("lane_count", 2)
    return RoadSegment.objects.create(road=road, **kw)


def _lane(segment=None, **kw):
    segment = segment or _segment()
    kw.setdefault("lane_number", 1)
    return Lane.objects.create(segment=segment, **kw)


class TestRoadModel(TestCase):
    def test_create_road(self):
        road = _road(name="Main Street")
        self.assertEqual(road.name, "Main Street")
        self.assertTrue(road.is_active)
        self.assertIsNotNone(road.created_at)
        self.assertIsNotNone(road.updated_at)

    def test_road_str(self):
        road = _road(name="Oak Avenue")
        self.assertEqual(str(road), "Oak Avenue")

    def test_road_name_unique(self):
        _road(name="Unique Road")
        with self.assertRaises(IntegrityError):
            _road(name="Unique Road")

    def test_road_default_is_active(self):
        road = _road()
        self.assertTrue(road.is_active)

    def test_road_types_choices(self):
        for choice, _ in Road.RoadType.choices:
            road = Road.objects.create(name=f"Road {choice}", road_type=choice)
            self.assertEqual(road.road_type, choice)

    def test_road_ordering(self):
        _road(name="Z Road")
        _road(name="A Road")
        names = list(Road.objects.values_list("name", flat=True))
        self.assertEqual(names, sorted(names))


class TestIntersectionModel(TestCase):
    def test_create_intersection(self):
        i = _intersection(name="Main/Oak", latitude=10.0, longitude=20.0)
        self.assertEqual(i.name, "Main/Oak")
        self.assertEqual(i.latitude, 10.0)
        self.assertTrue(i.is_active)

    def test_intersection_str(self):
        i = _intersection(name="Test Jct")
        self.assertIn("Test Jct", str(i))

    def test_intersection_nullable_coords(self):
        i = _intersection(name="No Coords")
        self.assertIsNone(i.latitude)
        self.assertIsNone(i.longitude)

    def test_invalid_latitude_raises(self):
        i = _intersection(name="BadLat")
        i.latitude = 200.0
        with self.assertRaises(ValidationError):
            i.full_clean()

    def test_invalid_longitude_raises(self):
        i = _intersection(name="BadLon")
        i.longitude = -200.0
        with self.assertRaises(ValidationError):
            i.full_clean()


class TestRoadSegmentModel(TestCase):
    def setUp(self):
        self.road = _road()
        self.i1 = _intersection(name="Start")
        self.i2 = _intersection(name="End")

    def test_create_segment(self):
        seg = _segment(
            road=self.road,
            speed_limit_kmh=60,
            lane_count=3,
            start_intersection=self.i1,
            end_intersection=self.i2,
        )
        self.assertEqual(seg.road, self.road)
        self.assertEqual(seg.speed_limit_kmh, 60)
        self.assertEqual(seg.lane_count, 3)
        self.assertEqual(seg.start_intersection, self.i1)
        self.assertEqual(seg.end_intersection, self.i2)

    def test_segment_str_contains_road_name(self):
        seg = _segment(road=self.road)
        self.assertIn(self.road.name, str(seg))

    def test_segment_nullable_intersections(self):
        seg = _segment(road=self.road)
        self.assertIsNone(seg.start_intersection)
        self.assertIsNone(seg.end_intersection)

    def test_segment_default_direction(self):
        seg = _segment(road=self.road)
        self.assertEqual(seg.direction, RoadSegment.Direction.BIDIRECTIONAL)

    def test_segment_invalid_speed_raises(self):
        seg = _segment(road=self.road)
        seg.speed_limit_kmh = 0
        with self.assertRaises(ValidationError):
            seg.full_clean()

    def test_segment_is_active_default(self):
        seg = _segment(road=self.road)
        self.assertTrue(seg.is_active)

    def test_road_protect_on_delete(self):
        """Road cannot be deleted if it has segments."""
        road = _road(name="Protected Road")
        _segment(road=road)
        from django.db import models as djm
        from django.db.models.deletion import ProtectedError
        with self.assertRaises(ProtectedError):
            road.delete()


class TestLaneModel(TestCase):
    def setUp(self):
        self.segment = _segment()

    def test_create_lane(self):
        lane = _lane(segment=self.segment, lane_number=1,
                     lane_type=Lane.LaneType.TRAVEL)
        self.assertEqual(lane.lane_number, 1)
        self.assertEqual(lane.lane_type, Lane.LaneType.TRAVEL)
        self.assertTrue(lane.is_active)

    def test_lane_str_contains_lane_number(self):
        lane = _lane(segment=self.segment, lane_number=2)
        self.assertIn("2", str(lane))

    def test_unique_together_segment_lane_number(self):
        _lane(segment=self.segment, lane_number=1)
        with self.assertRaises(IntegrityError):
            _lane(segment=self.segment, lane_number=1)

    def test_different_segments_can_share_lane_number(self):
        seg2 = _segment(_road(name="Road 2"))
        _lane(segment=self.segment, lane_number=1)
        lane2 = _lane(segment=seg2, lane_number=1)
        self.assertEqual(lane2.lane_number, 1)

    def test_lane_types_all_valid(self):
        for i, (choice, _) in enumerate(Lane.LaneType.choices, start=1):
            seg = _segment(_road(name=f"Road {i}"))
            lane = Lane.objects.create(segment=seg, lane_number=1, lane_type=choice)
            self.assertEqual(lane.lane_type, choice)

    def test_segment_protect_on_delete(self):
        from django.db.models.deletion import ProtectedError
        _lane(segment=self.segment, lane_number=1)
        with self.assertRaises(ProtectedError):
            self.segment.delete()
