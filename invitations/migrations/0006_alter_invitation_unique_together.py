# Generated by Django 4.0.4 on 2022-06-21 19:05

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("invitations", "0005_alter_invitation_unique_together"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="invitation",
            unique_together=set(),
        ),
    ]
