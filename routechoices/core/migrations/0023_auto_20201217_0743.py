# Generated by Django 3.1.3 on 2020-12-17 07:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0022_notice'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notice',
            name='text',
            field=models.CharField(blank=True, help_text='This will be displayed on the event page.', max_length=280),
        ),
    ]
