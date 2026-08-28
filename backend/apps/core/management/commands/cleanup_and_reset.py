"""
Management command: cleanup_and_reset

Removes all seeded/fabricated demo data and test verification users.
Leaves only:
    - The 8 intentional RBAC seed accounts (admin, Admin, tco, analyst,
        law, camtech, payofficer, publicuser)
    - The ai_service system account
    - Audit events (read-only record; preserved for integrity)

All seeded demo cameras (including any legacy demo webcams) and
their associated measurements are removed by this command.

Everything else — Nairobi roads, intersections, segments, lanes,
CAM-001 through CAM-005, sensors, all seeded incidents/events/signals,
all seeded/AI-test measurements from test cameras, analytics summaries,
and test/verification users — is deleted.

Usage:
    python manage.py cleanup_and_reset
    python manage.py cleanup_and_reset --dry-run   # preview, no changes
"""

from django.core.management.base import BaseCommand


KEEP_USERNAMES = {
    "admin", "Admin", "tco", "analyst", "law",
    "camtech", "payofficer", "publicuser", "ai_service",
}

KEEP_CAMERA_NAME = None  # WEBCAM-001 legacy removed; do not keep any seeded webcam


class Command(BaseCommand):
    help = "Remove all fabricated Nairobi demo data and test verification users."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Show what would be deleted without making changes.",
        )

    def handle(self, *args, **options):
        dry = options["dry_run"]
        tag = "[DRY RUN] " if dry else ""

        self.stdout.write(
            self.style.WARNING(f"\n{'DRY RUN — ' if dry else ''}Cleanup starting...\n")
        )

        self._clean_users(dry, tag)
        self._clean_cameras_and_sensors(dry, tag)
        self._clean_measurements(dry, tag)   # before cameras/roads deleted
        self._clean_traffic(dry, tag)        # signals/incidents before intersections
        self._clean_roads(dry, tag)          # roads/intersections last
        self._clean_analytics(dry, tag)

        if dry:
            self.stdout.write(self.style.WARNING("\nDry run complete — nothing was changed.\n"))
        else:
            self.stdout.write(self.style.SUCCESS(
                "\nCleanup complete.\n"
                "  Remaining cameras: none (no seeded webcam retained)\n"
                "  Remaining roads/intersections: none (no real Gondar data yet)\n"
                "  Retained users: admin, Admin, tco, analyst, law, "
                "camtech, payofficer, publicuser, ai_service\n"
            ))

    # ──────────────────────────────────────────────────────────────────
    # Users
    # ──────────────────────────────────────────────────────────────────
    def _clean_users(self, dry, tag):
        from django.contrib.auth import get_user_model
        U = get_user_model()

        to_delete = U.objects.exclude(username__in=KEEP_USERNAMES)
        names = list(to_delete.values_list("username", flat=True))
        count = to_delete.count()

        self.stdout.write(f"\n{tag}USERS — deleting {count} test/verification accounts:")
        for n in sorted(names):
            self.stdout.write(f"    - {n}")

        if not dry:
            to_delete.delete()
        self.stdout.write(
            self.style.SUCCESS(f"  {tag}Removed {count} users.")
            if count else "  No test users to remove."
        )

    # ──────────────────────────────────────────────────────────────────
    # Cameras & Sensors
    # ──────────────────────────────────────────────────────────────────
    def _clean_cameras_and_sensors(self, dry, tag):
        from apps.cameras.models import (
            Camera, CameraHealth, CameraCredential,
            Sensor, SensorHealth,
        )

        # Delete all seeded cameras (no special-case retention)
        cams_to_delete = Camera.objects.all()
        cam_names = list(cams_to_delete.values_list("name", flat=True))
        cam_count = cams_to_delete.count()
        self.stdout.write(f"\n{tag}CAMERAS — deleting {cam_count} seeded cameras:")
        for n in sorted(cam_names):
            self.stdout.write(f"    - {n}")
        if not dry:
            # CameraHealth and CameraCredential cascade-delete with the camera
            cams_to_delete.delete()

        # No special-case webcam retention or health reset — browser webcam is transient

        # Delete all sensors (all are seeded Nairobi sensors)
        sensor_count = Sensor.objects.count()
        self.stdout.write(f"\n{tag}SENSORS — deleting {sensor_count} seeded sensors:")
        for s in Sensor.objects.values_list("name", flat=True):
            self.stdout.write(f"    - {s}")
        if not dry:
            Sensor.objects.all().delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"  {tag}Removed {cam_count} cameras, {sensor_count} sensors."
            )
        )

    # ──────────────────────────────────────────────────────────────────
    # Roads, Intersections, Segments, Lanes
    # ──────────────────────────────────────────────────────────────────
    def _clean_roads(self, dry, tag):
        from apps.roads.models import Road, Intersection, RoadSegment, Lane

        r_count   = Road.objects.count()
        i_count   = Intersection.objects.count()
        s_count   = RoadSegment.objects.count()
        l_count   = Lane.objects.count()

        self.stdout.write(f"\n{tag}ROADS — deleting all Nairobi fabricated data:")
        self.stdout.write(f"    Roads: {r_count}, Intersections: {i_count}, "
                          f"Segments: {s_count}, Lanes: {l_count}")
        for r in Road.objects.values_list("name", flat=True):
            self.stdout.write(f"    Road: {r}")
        for i in Intersection.objects.values_list("name", flat=True):
            self.stdout.write(f"    Intersection: {i}")

        if not dry:
            # Order matters for FK constraints
            Lane.objects.all().delete()
            RoadSegment.objects.all().delete()
            Intersection.objects.all().delete()
            Road.objects.all().delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"  {tag}Removed {r_count} roads, {i_count} intersections, "
                f"{s_count} segments, {l_count} lanes."
            )
        )

    # ──────────────────────────────────────────────────────────────────
    # Traffic Incidents, Events, Signals, Phases
    # ──────────────────────────────────────────────────────────────────
    def _clean_traffic(self, dry, tag):
        from apps.traffic.models import (
            TrafficIncident, TrafficEvent, TrafficSignal, SignalPhase,
        )

        inc_count  = TrafficIncident.objects.count()
        evt_count  = TrafficEvent.objects.count()
        sig_count  = TrafficSignal.objects.count()
        ph_count   = SignalPhase.objects.count()

        self.stdout.write(f"\n{tag}TRAFFIC — deleting all seeded data:")
        self.stdout.write(f"    Incidents: {inc_count}, Events: {evt_count}, "
                          f"Signals: {sig_count}, Phases: {ph_count}")

        if not dry:
            SignalPhase.objects.all().delete()
            TrafficSignal.objects.all().delete()
            TrafficIncident.objects.all().delete()
            TrafficEvent.objects.all().delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"  {tag}Removed {inc_count} incidents, {evt_count} events, "
                f"{sig_count} signals, {ph_count} phases."
            )
        )

    # ──────────────────────────────────────────────────────────────────
    # Measurements
    # ──────────────────────────────────────────────────────────────────
    def _clean_measurements(self, dry, tag):
        from apps.traffic.models import TrafficMeasurement
        from apps.cameras.models import Camera

        # Drop all measurements (no special-case preservation for legacy webcams).
        total = TrafficMeasurement.objects.count()
        del_qs = TrafficMeasurement.objects.all()
        del_c = del_qs.count()

        self.stdout.write(f"\n{tag}MEASUREMENTS — total: {total}")
        self.stdout.write(f"    Deleting: {del_c} (all seeded and test measurements)")

        if not dry:
            del_qs.delete()

        self.stdout.write(
            self.style.SUCCESS(f"  {tag}Removed {del_c} measurements.")
        )

    # ──────────────────────────────────────────────────────────────────
    # Analytics summaries
    # ──────────────────────────────────────────────────────────────────
    def _clean_analytics(self, dry, tag):
        from apps.analytics.models import TrafficFlowSummary, IncidentReport, ViolationSummary

        f_count = TrafficFlowSummary.objects.count()
        i_count = IncidentReport.objects.count()
        v_count = ViolationSummary.objects.count()

        self.stdout.write(f"\n{tag}ANALYTICS — deleting all seeded summaries:")
        self.stdout.write(f"    FlowSummaries: {f_count}, IncidentReports: {i_count}, "
                          f"ViolationSummaries: {v_count}")

        if not dry:
            TrafficFlowSummary.objects.all().delete()
            IncidentReport.objects.all().delete()
            ViolationSummary.objects.all().delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"  {tag}Removed {f_count} flow summaries, {i_count} incident reports, "
                f"{v_count} violation summaries."
            )
        )
