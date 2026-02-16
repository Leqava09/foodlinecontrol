# Generated manually 
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('costing', '0012_auto_20260212_1242'),
    ]

    operations = [
        migrations.AddField(
            model_name='salarycosting',
            name='percentage_bonus',
            field=models.DecimalField(decimal_places=2, default=0, help_text='Bonus percentage to apply to price per unit', max_digits=5, verbose_name='% Bonus'),
        ),
        migrations.AddField(
            model_name='salarycosting',
            name='production_months',
            field=models.PositiveIntegerField(default=12, help_text='Number of months to distribute bonus over', verbose_name='Production Months'),
        ),
    ]
