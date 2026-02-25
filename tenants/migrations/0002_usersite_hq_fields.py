# Generated migration to add missing UserSite fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='usersite',
            name='hq_username',
            field=models.CharField(
                blank=True,
                help_text='Unique HQ login username. Only for HQ users.',
                max_length=150,
                null=True,
                unique=True
            ),
        ),
        migrations.AddField(
            model_name='usersite',
            name='hq_password',
            field=models.CharField(
                blank=True,
                help_text='HQ login password (encrypted with PBKDF2). Only for HQ users.',
                max_length=255,
                null=True
            ),
        ),
        migrations.AddField(
            model_name='usersite',
            name='is_manager',
            field=models.BooleanField(
                default=False,
                help_text='Site Manager'
            ),
        ),
        migrations.AddField(
            model_name='usersite',
            name='is_archived',
            field=models.BooleanField(
                default=False,
                db_index=True
            ),
        ),
    ]
