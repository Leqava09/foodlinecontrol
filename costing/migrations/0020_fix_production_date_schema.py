from django.db import migrations, connection


class Migration(migrations.Migration):

    dependencies = [
        ('costing', '0019_batchcosting_investor_loan_costing_and_more'),
    ]

    def fix_production_date_column(apps, schema_editor):
        with connection.cursor() as cursor:
            # Drop the foreign key constraint if it exists
            cursor.execute("""
                ALTER TABLE costing_batchcosting 
                DROP CONSTRAINT IF EXISTS costing_batchcosting_production_date_id_fkey
            """)
            
            # Change column type from DATE to INTEGER, setting NULL for existing date values
            cursor.execute("""
                ALTER TABLE costing_batchcosting 
                ALTER COLUMN production_date_id TYPE integer USING NULL
            """)
            
            # Add the correct foreign key constraint
            cursor.execute("""
                ALTER TABLE costing_batchcosting 
                ADD CONSTRAINT costing_batchcosting_production_date_id_fkey 
                FOREIGN KEY (production_date_id) REFERENCES manufacturing_production(id) ON DELETE CASCADE
            """)

    operations = [
        migrations.RunPython(fix_production_date_column),
    ]
