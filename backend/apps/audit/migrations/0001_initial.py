import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="AuditEvent",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "timestamp",
                    models.DateTimeField(auto_now_add=True, db_index=True),
                ),
                ("actor_id", models.IntegerField(blank=True, db_index=True, null=True)),
                (
                    "actor_username",
                    models.CharField(blank=True, max_length=150, null=True),
                ),
                ("action", models.CharField(db_index=True, max_length=128)),
                (
                    "target_type",
                    models.CharField(blank=True, max_length=128, null=True),
                ),
                (
                    "target_id",
                    models.CharField(blank=True, max_length=64, null=True),
                ),
                (
                    "ip_address",
                    models.GenericIPAddressField(blank=True, null=True),
                ),
                ("user_agent", models.TextField(blank=True, null=True)),
                (
                    "outcome",
                    models.CharField(
                        choices=[
                            ("success", "Success"),
                            ("failure", "Failure"),
                            ("denied", "Denied"),
                        ],
                        db_index=True,
                        default="success",
                        max_length=16,
                    ),
                ),
                ("detail", models.JSONField(blank=True, null=True)),
            ],
            options={
                "verbose_name": "Audit Event",
                "verbose_name_plural": "Audit Events",
                "ordering": ["-timestamp"],
            },
        ),
        migrations.AddIndex(
            model_name="auditevent",
            index=models.Index(
                fields=["timestamp", "actor_id", "action"],
                name="audit_ts_actor_action_idx",
            ),
        ),
    ]
