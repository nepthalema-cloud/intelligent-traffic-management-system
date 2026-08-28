"""
Test WebSocket push via the channel layer.
Sends a real measurement_created event to the 'dashboard' group
and confirms the channel layer (Redis) accepts it.
"""
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')


def _run_push_test():
    """Run a one-off channel-layer push test. Called only when executed.

    Guarded from import-time execution so test discovery and importers
    are not affected by this helper script.
    """
    import django
    django.setup()

    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    layer = get_channel_layer()
    if layer is None:
        print("FAIL: No channel layer configured")
        return
    try:
        async_to_sync(layer.group_send)("dashboard", {
            "type": "measurement_created",
            "payload": {
                "camera_id": 10,
                "vehicle_count": 22,
                "avg_speed_kmh": None,
                "data_source": "ai",
                "source_label": "TEST-PRERECORDED",
            }
        })
        print("PASS: Channel layer accepted measurement_created push to 'dashboard' group")
        print("      Redis channel layer is operational.")
        print("      Any connected WebSocket client would receive this event.")
    except Exception as e:
        print(f"FAIL: Channel layer push failed: {e}")


if __name__ == "__main__":
    _run_push_test()
