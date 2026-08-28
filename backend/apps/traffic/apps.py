from django.apps import AppConfig


class TrafficConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.traffic"
    verbose_name = "Traffic Management"

    def ready(self):
        import apps.traffic.signals  # noqa: F401 — register post_save signal
