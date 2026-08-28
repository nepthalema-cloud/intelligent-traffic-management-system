#!/usr/bin/env python
"""Full database audit script — run with: python manage.py runscript audit_db
   OR: python audit_db.py (from backend/ with DJANGO_SETTINGS_MODULE set)
"""
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
django.setup()

from django.contrib.auth import get_user_model

U = get_user_model()

# ── USERS ────────────────────────────────────────────────────────────────────
print("\n" + "="*80)
print("USERS")
print("="*80)
users = U.objects.prefetch_related("groups").order_by("date_joined")
print(f"Total: {users.count()}")
for u in users:
    g = [x.name for x in u.groups.all()]
    print(f"  {u.id:3} | {u.username:<18} | staff={u.is_staff} super={u.is_superuser} active={u.is_active} | {u.date_joined.date()} | {g}")

# ── CAMERAS ──────────────────────────────────────────────────────────────────
print("\n" + "="*80)
print("CAMERAS")
print("="*80)
from apps.cameras.models import Camera, CameraHealth
cams = Camera.objects.select_related("intersection", "segment").order_by("id")
print(f"Total: {cams.count()}")
for c in cams:
    try:
        h = c.health
        health = f"health={h.health_status} conn={h.connectivity_status}"
    except Exception:
        health = "no health record"
    loc = c.intersection.name if c.intersection_id else (c.segment.name if c.segment_id else "unassigned")
    print(f"  {c.id:3} | {c.name:<15} | type={c.camera_type:<10} | ip={c.ip_address or 'none':<16} | url={c.stream_url or 'none':<45} | {health} | loc={loc}")

# ── ROADS ────────────────────────────────────────────────────────────────────
print("\n" + "="*80)
print("ROADS")
print("="*80)
from apps.roads.models import Road, Intersection, RoadSegment
roads = Road.objects.order_by("id")
print(f"Total: {roads.count()}")
for r in roads:
    print(f"  {r.id:3} | {r.name:<35} | type={r.road_type}")

print("\nINTERSECTIONS")
ints = Intersection.objects.order_by("id")
print(f"Total: {ints.count()}")
for i in ints:
    print(f"  {i.id:3} | {i.name:<45} | lat={i.latitude} lon={i.longitude}")

print("\nSEGMENTS")
segs = RoadSegment.objects.order_by("id")
print(f"Total: {segs.count()}")
for s in segs:
    print(f"  {s.id:3} | {s.name:<35} | road={s.road.name}")

# ── TRAFFIC SIGNALS ──────────────────────────────────────────────────────────
print("\n" + "="*80)
print("TRAFFIC SIGNALS")
print("="*80)
from apps.traffic.models import TrafficSignal
sigs = TrafficSignal.objects.select_related("intersection").order_by("id")
print(f"Total: {sigs.count()}")
for s in sigs:
    print(f"  {s.id:3} | {s.name:<20} | intersection={s.intersection.name if s.intersection_id else 'none'}")

# ── INCIDENTS ────────────────────────────────────────────────────────────────
print("\n" + "="*80)
print("INCIDENTS")
print("="*80)
from apps.traffic.models import TrafficIncident
incs = TrafficIncident.objects.order_by("occurred_at")
print(f"Total: {incs.count()}")
for i in incs:
    print(f"  {i.id:3} | {i.title[:55]:<55} | state={i.state:<12} | {i.occurred_at.date()}")

# ── EVENTS ───────────────────────────────────────────────────────────────────
print("\n" + "="*80)
print("EVENTS")
print("="*80)
from apps.traffic.models import TrafficEvent
evts = TrafficEvent.objects.order_by("occurred_at")
print(f"Total: {evts.count()}")
for e in evts:
    print(f"  {e.id:3} | type={e.event_type:<15} | active={e.is_active} | {str(e.description[:50]):<50} | {e.occurred_at.date()}")

# ── MEASUREMENTS ─────────────────────────────────────────────────────────────
print("\n" + "="*80)
print("MEASUREMENTS (summary)")
print("="*80)
from apps.traffic.models import TrafficMeasurement
from django.db.models import Count, Min, Max
mcount = TrafficMeasurement.objects.count()
if mcount > 0:
    agg = TrafficMeasurement.objects.aggregate(
        total=Count("id"), first=Min("measured_at"), last=Max("measured_at")
    )
    by_cam = TrafficMeasurement.objects.values("camera__name", "sensor__name").annotate(n=Count("id")).order_by("-n")
    print(f"Total: {agg['total']}  |  First: {agg['first']}  |  Last: {agg['last']}")
    for b in by_cam:
        src = b["camera__name"] or b["sensor__name"] or "unknown"
        print(f"  source={src:<20} count={b['n']}")
else:
    print("  No measurements.")

# ── VIOLATIONS ───────────────────────────────────────────────────────────────
print("\n" + "="*80)
print("VIOLATIONS")
print("="*80)
from apps.violations.models import Violation
viols = Violation.objects.order_by("occurred_at")
print(f"Total: {viols.count()}")
for v in viols:
    print(f"  {v.id} | type={v.violation_type} | conf={v.confidence} | cam={v.camera_id} | {v.occurred_at.date()}")

# ── ANALYTICS ────────────────────────────────────────────────────────────────
print("\n" + "="*80)
print("ANALYTICS")
print("="*80)
from apps.analytics.models import TrafficFlowSummary, IncidentReportSummary, ViolationSummary
print(f"Flow summaries:     {TrafficFlowSummary.objects.count()}")
print(f"Incident summaries: {IncidentReportSummary.objects.count()}")
print(f"Violation summaries:{ViolationSummary.objects.count()}")

# ── AUDIT EVENTS ─────────────────────────────────────────────────────────────
print("\n" + "="*80)
print("AUDIT EVENTS (summary)")
print("="*80)
from apps.audit.models import AuditEvent
from django.db.models import Count
ac = AuditEvent.objects.count()
print(f"Total audit events: {ac}")
if ac > 0:
    by_action = AuditEvent.objects.values("action").annotate(n=Count("id")).order_by("-n")[:10]
    for a in by_action:
        print(f"  action={a['action']:<30} n={a['n']}")

print("\n" + "="*80)
print("AUDIT COMPLETE")
print("="*80)
