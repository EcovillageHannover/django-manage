# Generated by Django 3.1.3 on 2021-03-28 19:33

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('account', '0008_userprofile_mailinglist_mail'),
    ]

    operations = [
        migrations.AddField(
            model_name='groupprofile',
            name='editable',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='groupprofile',
            name='parent',
            field=models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='children', to='auth.group'),
        ),
    ]