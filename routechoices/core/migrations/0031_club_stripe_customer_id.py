# Generated by Django 3.2 on 2021-06-03 11:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0030_auto_20210303_1805'),
    ]

    operations = [
        migrations.AddField(
            model_name='club',
            name='stripe_customer_id',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
