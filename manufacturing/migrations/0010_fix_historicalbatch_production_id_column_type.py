# Generated manually to fix HistoricalBatch production_id column type

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('manufacturing', '0009_alter_batch_a_no_alter_batch_batch_number_and_more'),
    ]

    operations = [
        # First, drop all foreign key constraints
        migrations.RunSQL(
            sql=[
                "ALTER TABLE manufacturing_historicalbatch DROP CONSTRAINT IF EXISTS manufacturing_historical_5a82b4a9_fk_manufactu;",
                "ALTER TABLE manufacturing_historicalbatch DROP CONSTRAINT IF EXISTS manufacturing_historicalbatch_production_id_fkey;",
            ],
            reverse_sql=migrations.RunSQL.noop,
        ),
        
        # Rename the broken date column
        migrations.RunSQL(
            sql="ALTER TABLE manufacturing_historicalbatch RENAME COLUMN production_id TO production_id_old;",
            reverse_sql="ALTER TABLE manufacturing_historicalbatch RENAME COLUMN production_id_old TO production_id;",
        ),
        
        # Create new integer production_id column
        migrations.RunSQL(
            sql="ALTER TABLE manufacturing_historicalbatch ADD COLUMN production_id INTEGER;",
            reverse_sql="ALTER TABLE manufacturing_historicalbatch DROP COLUMN IF EXISTS production_id;",
        ),
        
        # Copy data from old date column to new integer column by matching with Production
        migrations.RunSQL(
            sql="""
                UPDATE manufacturing_historicalbatch h 
                SET production_id = p.id 
                FROM manufacturing_production p 
                WHERE h.production_id_old = p.production_date
                  AND (h.site_id = p.site_id OR (h.site_id IS NULL AND p.site_id IS NULL));
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
        
        # Drop the old column
        migrations.RunSQL(
            sql="ALTER TABLE manufacturing_historicalbatch DROP COLUMN production_id_old;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        
        # Add the foreign key constraint back
        migrations.RunSQL(
            sql="""
                ALTER TABLE manufacturing_historicalbatch 
                ADD CONSTRAINT manufacturing_historicalbatch_production_id_fkey 
                FOREIGN KEY (production_id) 
                REFERENCES manufacturing_production(id) 
                ON DELETE SET NULL;
            """,
            reverse_sql="ALTER TABLE manufacturing_historicalbatch DROP CONSTRAINT IF EXISTS manufacturing_historicalbatch_production_id_fkey;",
        ),
    ]
