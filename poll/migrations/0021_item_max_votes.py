# Generated by Django 3.1.3 on 2020-12-29 16:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('poll', '0020_auto_20201127_2028'),
    ]

    operations = [
        migrations.AddField(
            model_name='item',
            name='max_votes',
            field=models.SmallIntegerField(blank=True, default=-1, null=True),
        ),
    ]
