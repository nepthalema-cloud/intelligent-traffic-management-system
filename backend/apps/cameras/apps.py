from django.apps import AppConfig


class CamerasConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.cameras"
    verbose_name = "Cameras & Sensors"

    def ready(self):
        """
        Start the background camera health probe thread.

        This runs every 60s independent of Celery, providing resilient health
        monitoring even when Celery has Python 3.14 compatibility issues.

        Only starts in the main ASGI process (not during migrations).
        """
        import os
        # RUN_MAIN is set by Django's dev server; we check for Daphne too
        # by testing whether we're NOT in a management command context.
        run_main = os.environ.get("RUN_MAIN") == "true"
        is_asgi  = "daphne" in " ".join(
            __import__("sys").argv
        ).lower() if __import__("sys").argv else False
        is_worker = os.environ.get("CAMERA_HEALTH_WORKER", "").lower() in ("1", "true")

        if run_main or is_asgi or is_worker:
            from apps.cameras.health_worker import start as start_health_worker
            start_health_worker()
