# Generated by Django 4.1 on 2022-08-08 12:04

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0022_rename__locations_count_device__location_count"),
    ]

    operations = [
        migrations.CreateModel(
            name="Queclink300Command",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("creation_date", models.DateTimeField(auto_now_add=True)),
                ("modification_date", models.DateTimeField(auto_now=True)),
                ("sent", models.BooleanField(default=False)),
                ("command", models.TextField()),
                (
                    "target",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="commands",
                        to="core.imeidevice",
                    ),
                ),
            ],
            options={
                "verbose_name": "Queclink command",
                "verbose_name_plural": "Queclink commands",
                "ordering": ["-modification_date"],
            },
        ),
    ]
