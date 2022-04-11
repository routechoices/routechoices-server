# Generated by Django 4.0.3 on 2022-04-11 06:34

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0006_device_battery_level"),
    ]

    operations = [
        migrations.AlterField(
            model_name="device",
            name="battery_level",
            field=models.PositiveIntegerField(
                default=None,
                null=True,
                validators=[django.core.validators.MaxValueValidator(100)],
            ),
        ),
    ]
