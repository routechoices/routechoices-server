# Generated by Django 4.2.4 on 2023-08-30 09:37

from django.db import migrations

import routechoices.core.models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0054_event_list_on_routechoices_com_alter_event_privacy"),
    ]

    operations = [
        migrations.AlterField(
            model_name="event",
            name="backdrop_map",
            field=routechoices.core.models.BackroundMapChoicesField(
                default="blank", max_length=16, verbose_name="Background map"
            ),
        ),
    ]