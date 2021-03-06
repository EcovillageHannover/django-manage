# Generated by Django 2.2.11 on 2020-05-13 20:15

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    replaces = [('poll', '0002_poll_description'), ('poll', '0003_auto_20200513_1429'), ('poll', '0004_auto_20200513_1703'), ('poll', '0005_auto_20200513_1704')]

    dependencies = [
        ('poll', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='poll',
            name='description',
            field=models.TextField(default=''),
        ),
        migrations.AddField(
            model_name='poll',
            name='poll_type',
            field=models.CharField(choices=[('RA', 'Radiobox'), ('CE', 'Checkbox'), ('TX', 'Free Text')], default='RA', max_length=2),
        ),
        migrations.AddField(
            model_name='pollcollection',
            name='visible',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='pollcollection',
            name='visible_results',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AlterField(
            model_name='vote',
            name='item',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='poll.Item', verbose_name='voted item'),
        ),
        migrations.AddField(
            model_name='vote',
            name='text',
            field=models.TextField(blank=True, default=''),
        ),
    ]
