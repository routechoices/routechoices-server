# Generated by Django 4.0.1 on 2022-02-03 13:20

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0003_event_send_interval"),
    ]

    operations = [
        migrations.AlterField(
            model_name="event",
            name="send_interval",
            field=models.PositiveIntegerField(
                default=5,
                help_text="If you use dedicated trackers, enter here the sending interval you set your devices to, if you use the official smartphone app leave the value at 5 seconds",
                validators=[django.core.validators.MinValueValidator(1)],
                verbose_name="Send interval (seconds)",
            ),
        ),
    ]
