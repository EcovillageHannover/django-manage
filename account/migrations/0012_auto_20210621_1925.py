# Generated by Django 3.1.3 on 2021-06-21 19:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0011_groupprofile_parent'),
    ]

    operations = [
        migrations.AddField(
            model_name='groupprofile',
            name='synced_at',
            field=models.DateTimeField(blank=True, default=None, null=True),
        ),
        migrations.AddField(
            model_name='groupprofile',
            name='updated_at',
            field=models.DateTimeField(blank=True, default=None, null=True),
        ),
    ]