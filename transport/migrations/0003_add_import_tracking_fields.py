# Generated manually on 2026-02-12

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0001_initial'),
        ('transport', '0002_deliverysite_site_transportload_site'),
    ]

    operations = [
        migrations.AddField(
            model_name='transportload',
            name='import_source_site',
            field=models.ForeignKey(
                blank=True,
                help_text='Site this transport load was imported from (HQ only)',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='imported_transport_loads',
                to='tenants.site',
                verbose_name='Import Source Site'
            ),
        ),
        migrations.AddField(
            model_name='transportload',
            name='import_source_load_number',
            field=models.CharField(
                blank=True,
                help_text='Original load number from source site',
                max_length=50,
                null=True,
                verbose_name='Import Source Load Number'
            ),
        ),
    ]
