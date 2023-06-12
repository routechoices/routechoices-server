# Generated by Django 4.2 on 2023-05-26 11:53

from django.db import migrations, models

import routechoices.lib.validators


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0048_club_order_id"),
    ]

    operations = [
        migrations.AlterField(
            model_name="club",
            name="order_id",
            field=models.CharField(blank=True, default="", max_length=200),
        ),
        migrations.AlterField(
            model_name="club",
            name="slug_changed_from",
            field=models.CharField(
                blank=True,
                default="",
                editable=False,
                max_length=50,
                validators=[routechoices.lib.validators.validate_domain_slug],
            ),
        ),
        migrations.AlterField(
            model_name="event",
            name="emergency_contact",
            field=models.EmailField(
                blank=True,
                default="",
                help_text=(
                    "Email address of a person available to respond in the "
                    "case a competitor carrying a GPS tracker with SOS "
                    "feature enabled triggers the SOS button."
                ),
                max_length=254,
            ),
        ),
    ]