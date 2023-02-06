# Generated by Django 4.0.4 on 2022-05-02 06:18

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0008_alter_event_backdrop_map"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="tail_length",
            field=models.PositiveIntegerField(
                default=60, verbose_name="Tail length (seconds)"
            ),
        ),
    ]
