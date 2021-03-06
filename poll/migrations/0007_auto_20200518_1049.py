# Generated by Django 3.0.6 on 2020-05-18 10:49

from django.db import migrations
import taggit.managers


class Migration(migrations.Migration):

    dependencies = [
        ('taggit', '0003_taggeditem_add_unique_index'),
        ('poll', '0006_auto_20200518_1047'),
    ]

    operations = [
        migrations.AlterField(
            model_name='poll',
            name='tags',
            field=taggit.managers.TaggableManager(blank=True, help_text='A comma-separated list of tags.', through='taggit.TaggedItem', to='taggit.Tag', verbose_name='Tags'),
        ),
    ]
