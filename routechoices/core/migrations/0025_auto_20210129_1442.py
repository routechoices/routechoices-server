# Generated by Django 3.1.4 on 2021-01-29 14:42

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0024_auto_20210128_1128'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='mapassignation',
            options={'ordering': ['id']},
        ),
    ]
