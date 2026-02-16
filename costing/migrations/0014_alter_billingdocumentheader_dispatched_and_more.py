# Generated manually
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('costing', '0013_salarycosting_percentage_bonus_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='salarycosting',
            name='percentage_bonus',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=5, verbose_name='% Bonus'),
        ),
        migrations.AlterField(
            model_name='salarycosting',
            name='production_months',
            field=models.PositiveIntegerField(default=12, verbose_name='Production Months'),
        ),
    ]
