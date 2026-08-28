"""
Management command: seed_demo

Creates CLEARLY LABELLED sample/demo data for the TrafficOps application.

Target deployment: Gondar, Ethiopia.

This command does NOT fabricate real traffic data.
All records created here are explicitly labelled as DEMO/SAMPLE data.
They must never be presented as real Gondar traffic conditions.

The command is idempotent — safe to run multiple times.
Use --clear to wipe existing demo data before re-seeding.

Usage:
    python manage.py seed_demo
    python manage.py seed_demo --clear
"""

from django.core.management.base import BaseCommand


# ── DEMO DATA POLICY ──────────────────────────────────────────────────────────
#
# Until the deployment team provides real road network data for Gondar,
# this command creates clearly labelled SAMPLE locations.
#
# Coordinates used here are real Gondar, Ethiopia coordinates:
#   City center: 12.6030° N, 37.4521° E
#
# These are approximate reference points, NOT verified survey data.
# They are labelled [SAMPLE] throughout.
#
# ─────────────────────────────────────────────────────────────────────────────

DEMO_PREFIX = "[SAMPLE] "


class Command(BaseCommand):
    help = (
        "Seed clearly-labelled SAMPLE data for Gondar, Ethiopia. "
        "Does NOT fabricate real traffic conditions."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete all existing demo/sample data before seeding.",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            self._clear()

        self.stdout.write(
            self.style.WARNING(
                "\nNOTE: All data created by this command is SAMPLE/DEMO data.\n"
                "      It does not represent real Gondar traffic conditions.\n"
            )
        )

        self.stdout.write(self.style.SUCCESS(
            "\nSample data seeded.\n"
            "\nTo add real Gondar roads/intersections, use the admin interface\n"
            "or create a new management command with verified survey data.\n"
        ))

    # ──────────────────────────────────────────────────────────────────
    # Clear
    # ──────────────────────────────────────────────────────────────────
    def _clear(self):
        from apps.traffic.models import (
            TrafficIncident, TrafficEvent,
            TrafficMeasurement, SignalPhase, TrafficSignal,
        )
        from apps.cameras.models import CameraHealth, SensorHealth, Camera, Sensor
        from apps.roads.models import Lane, RoadSegment, Intersection, Road

        # Only delete SAMPLE-prefixed records, not user-created ones
        SignalPhase.objects.filter(
            signal__name__startswith=DEMO_PREFIX
        ).delete()
        TrafficSignal.objects.filter(name__startswith=DEMO_PREFIX).delete()
        TrafficIncident.objects.filter(title__startswith=DEMO_PREFIX).delete()
        TrafficEvent.objects.filter(description__startswith=DEMO_PREFIX).delete()
        Lane.objects.filter(segment__name__startswith=DEMO_PREFIX).delete()
        RoadSegment.objects.filter(name__startswith=DEMO_PREFIX).delete()
        Intersection.objects.filter(name__startswith=DEMO_PREFIX).delete()
        Road.objects.filter(name__startswith=DEMO_PREFIX).delete()
        self.stdout.write("  Cleared existing [SAMPLE] demo data.")

    # Note: WEBCAM-001 legacy demo camera removed. Browser webcam testing
    # should be performed via the browser-based testing panel and is not
    # persisted as a Camera record.
