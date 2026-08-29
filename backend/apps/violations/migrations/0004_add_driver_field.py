"""Add driver FK to Vehicle

Automatically generated migration to add an optional driver ForeignKey
to the Vehicle model so vehicles can be associated with the drivers
registry.
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("violations", "0003_phase5_ai_fields"),
        ("drivers", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehicle",
            name="driver",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="vehicles",
                to="drivers.driver",
            ),
        ),
    ]
