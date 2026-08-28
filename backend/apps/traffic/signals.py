"""
Django signals for the traffic app — Phase 5.

post_save on TrafficMeasurement: push real-time WebSocket event to dashboard
when the measurement source is 'ai' (real AI-generated data).

Demo/seed data is NOT pushed to avoid flooding the dashboard with noise.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender='traffic.TrafficMeasurement')
def measurement_created_push(sender, instance, created, **kwargs):
    """Push new AI measurements to WebSocket dashboard clients."""
    if not created:
        return
    if instance.data_source != 'ai':
        return  # Only push real AI measurements, not demo/seed data

    try:
        from apps.core.push import push_measurement
        push_measurement({
            "id":             instance.pk,
            "camera_id":      instance.camera_id,
            "camera_name":    instance.camera.name if instance.camera_id and instance.camera else None,
            "vehicle_count":  instance.vehicle_count,
            "avg_speed_kmh":  instance.avg_speed_kmh,
            "occupancy_pct":  instance.occupancy_pct,
            "data_source":    instance.data_source,
            "measured_at":    instance.measured_at.isoformat(),
            "source_label":   "TEST-PRERECORDED" if instance.camera and instance.camera.description.startswith("TEST") else "AI-LIVE",
        })
    except Exception:
        pass  # Never let push failures affect measurement persistence
