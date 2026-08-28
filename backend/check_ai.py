import django, os
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.development'
django.setup()
from apps.traffic.models import TrafficMeasurement
from apps.cameras.models import CameraHealth

ai = list(TrafficMeasurement.objects.filter(data_source='ai').order_by('-measured_at')[:8])
print(f'AI measurements in DB: {len(ai)}')
for m in ai:
    t = m.measured_at.strftime('%H:%M:%S')
    print(f'  id={m.pk} cam={m.camera_id} vehicles={m.vehicle_count} speed={m.avg_speed_kmh} src={m.data_source} at={t}')

total = TrafficMeasurement.objects.count()
ai_count = TrafficMeasurement.objects.filter(data_source='ai').count()
demo_count = TrafficMeasurement.objects.filter(data_source='demo').count()
print(f'Total: {total}  AI: {ai_count}  Demo: {demo_count}')

print('\nCamera health:')
for h in CameraHealth.objects.select_related('camera').all():
    print(f'  {h.camera.name}: {h.health_status}/{h.connectivity_status} last_seen={h.last_seen}')
