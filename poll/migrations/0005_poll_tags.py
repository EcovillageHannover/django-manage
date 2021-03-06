# Generated by Django 3.0.6 on 2020-05-15 22:34

from django.db import migrations
import taggit.managers


class Migration(migrations.Migration):

    dependencies = [
        ('taggit', '0003_taggeditem_add_unique_index'),
        ('poll', '0004_auto_20200515_2148'),
    ]

    operations = [
        migrations.AddField(
            model_name='poll',
            name='tags',
            field=taggit.managers.TaggableManager(help_text='A comma-separated list of tags.', through='taggit.TaggedItem', to='taggit.Tag', verbose_name='Tags'),
        ),
    ]
