# Generated by Django 3.1.1 on 2020-10-18 08:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0007_auto_20201008_1542'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='mailinglist_mail',
            field=models.EmailField(blank=True, max_length=100),
        ),
    ]
