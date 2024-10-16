# Generated by Django 4.1.2 on 2022-11-11 12:55

import django.db.models.deletion
from django.db import migrations, models

import routechoices.lib.helpers


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0030_alter_club_description"),
    ]

    operations = [
        migrations.CreateModel(
            name="EventSet",
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
                (
                    "aid",
                    models.CharField(
                        default=routechoices.lib.helpers.random_key,
                        editable=False,
                        max_length=12,
                        unique=True,
                    ),
                ),
                ("creation_date", models.DateTimeField(auto_now_add=True)),
                ("modification_date", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=255, verbose_name="Name")),
                (
                    "club",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="event_sets",
                        to="core.club",
                        verbose_name="Club",
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="event",
            name="event_set",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="events",
                to="core.eventset",
                verbose_name="Event Set",
            ),
        ),
    ]
