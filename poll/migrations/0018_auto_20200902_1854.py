# Generated by Django 3.1 on 2020-09-02 18:54

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('poll', '0017_auto_20200902_1812'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='pollcollection',
            options={'permissions': (('vote_pollcollection', 'Umfrage abstimmen'), ('analyze_pollcollection', 'Umfrage auswerten'), ('export_pollcollection', 'Umfragedaten exportieren')), 'verbose_name': 'Umfrage', 'verbose_name_plural': 'Umfragen'},
        ),
    ]