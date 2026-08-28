"""
Management command: run_analytics

Manually triggers analytics aggregation jobs for a specific date or the
previous day (default).  Intended for admin-triggered re-aggregation.

Usage:
    python manage.py run_analytics
    python manage.py run_analytics --date 2026-08-01
    python manage.py run_analytics --all  # re-run all four aggregations
"""

from datetime import datetime, timezone as dt_timezone, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Manually run analytics aggregation tasks."

    def add_arguments(self, parser):
        parser.add_argument("--date", type=str, default=None,
                            help="UTC date to aggregate (YYYY-MM-DD). Defaults to yesterday.")
        parser.add_argument("--flow-hourly", action="store_true",
                            help="Run hourly flow aggregation for every hour of --date.")
        parser.add_argument("--flow-daily", action="store_true",
                            help="Run daily flow aggregation for --date.")
        parser.add_argument("--incidents", action="store_true",
                            help="Run daily incident aggregation for --date.")
        parser.add_argument("--violations", action="store_true",
                            help="Run daily violation aggregation for --date.")
        parser.add_argument("--all", dest="all_tasks", action="store_true",
                            help="Run all four aggregations for --date.")

    def handle(self, *args, **options):
        from apps.analytics.services import (
            aggregate_flow_for_hour,
            aggregate_flow_for_day,
            aggregate_incidents_for_day,
            aggregate_violations_for_day,
        )

        if options["date"]:
            day_start = datetime.strptime(options["date"], "%Y-%m-%d").replace(
                tzinfo=dt_timezone.utc
            )
        else:
            day_start = (timezone.now() - timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )

        run_all = options["all_tasks"]

        if run_all or options["flow_hourly"]:
            total = 0
            for h in range(24):
                hour_start = day_start + timedelta(hours=h)
                total += aggregate_flow_for_hour(hour_start)
            self.stdout.write(f"  Hourly flow: {total} new summaries")

        if run_all or options["flow_daily"]:
            n = aggregate_flow_for_day(day_start)
            self.stdout.write(f"  Daily flow: {n} new summaries")

        if run_all or options["incidents"]:
            n = aggregate_incidents_for_day(day_start)
            self.stdout.write(f"  Incident reports: {n} new records")

        if run_all or options["violations"]:
            n = aggregate_violations_for_day(day_start)
            self.stdout.write(f"  Violation summaries: {n} new records")

        self.stdout.write(self.style.SUCCESS(
            f"Analytics aggregation complete for {day_start.date()}."
        ))
