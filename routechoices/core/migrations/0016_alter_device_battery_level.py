# Generated by Django 4.0.4 on 2022-06-08 12:40

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0015_alter_deviceclubownership_options"),
    ]

    operations = [
        migrations.AlterField(
            model_name="device",
            name="battery_level",
            field=models.PositiveIntegerField(
                blank=True,
                default=None,
                null=True,
                validators=[django.core.validators.MaxValueValidator(100)],
            ),
        ),
    ]