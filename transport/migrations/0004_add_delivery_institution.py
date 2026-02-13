# Generated manually on 2026-02-12

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('transport', '0003_add_import_tracking_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='transportload',
            name='delivery_institution',
            field=models.ForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='transport_loads',
                to='transport.deliverysite',
                verbose_name='Delivery Institution'
            ),
        ),
    ]
