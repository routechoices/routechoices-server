# Generated by Django 4.1 on 2022-08-08 12:07

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0023_queclink300command"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="Queclink300Command",
            new_name="QueclinkCommand",
        ),
    ]
