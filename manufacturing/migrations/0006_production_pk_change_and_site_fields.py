# Generated manually for Production primary key change

import django.db.models.deletion
from django.db import migrations, models


def create_production_id(apps, schema_editor):
    """Add sequential IDs to existing production records"""
    Production = apps.get_model('manufacturing', 'Production')
    for i, prod in enumerate(Production.objects.all().order_by('production_date'), 1):
        Production.objects.filter(production_date=prod.production_date).update(id=i)


class Migration(migrations.Migration):

    dependencies = [
        ('manufacturing', '0005_stockusagereport'),
        ('tenants', '0001_initial'),
    ]

    operations = [
        # Step 1: Add site field to batch and historicalbatch (these don't have PK issues)
        migrations.AddField(
            model_name='batch',
            name='site',
            field=models.ForeignKey(
                blank=True, 
                help_text='Manufacturing site for this batch', 
                null=True, 
                on_delete=django.db.models.deletion.PROTECT, 
                related_name='batches', 
                to='tenants.site'
            ),
        ),
        migrations.AddField(
            model_name='historicalbatch',
            name='site',
            field=models.ForeignKey(
                blank=True, 
                db_constraint=False, 
                help_text='Manufacturing site for this batch', 
                null=True, 
                on_delete=django.db.models.deletion.DO_NOTHING, 
                related_name='+', 
                to='tenants.site'
            ),
        ),
        
        # Step 2: For Production, we need to handle the primary key change with raw SQL
        migrations.RunSQL(
            # Forward SQL
            sql=[
                # Drop dependent foreign key constraints first
                "ALTER TABLE manufacturing_batch DROP CONSTRAINT IF EXISTS manufacturing_batch_production_id_722b24fd_fk_manufactu;",
                "ALTER TABLE manufacturing_batch DROP CONSTRAINT IF EXISTS manufacturing_batch_production_id_fkey;",
                "ALTER TABLE costing_batchcosting DROP CONSTRAINT IF EXISTS costing_batchcosting_production_date_id_cc89e7ec_fk_manufactu;",
                "ALTER TABLE costing_batchcosting DROP CONSTRAINT IF EXISTS costing_batchcosting_production_date_id_fkey;",
                # Drop the existing primary key constraint
                "ALTER TABLE manufacturing_production DROP CONSTRAINT manufacturing_production_pkey CASCADE;",
                # Add the id column as a serial (auto-increment)
                "ALTER TABLE manufacturing_production ADD COLUMN id SERIAL;",
                # Make id the new primary key
                "ALTER TABLE manufacturing_production ADD PRIMARY KEY (id);",
            ],
            # Reverse SQL
            reverse_sql=[
                "ALTER TABLE manufacturing_production DROP CONSTRAINT manufacturing_production_pkey;",
                "ALTER TABLE manufacturing_production DROP COLUMN id;",
                "ALTER TABLE manufacturing_production ADD PRIMARY KEY (production_date);",
            ]
        ),
        
        # Step 3: Add site field to Production
        migrations.AddField(
            model_name='production',
            name='site',
            field=models.ForeignKey(
                blank=True, 
                help_text='Manufacturing site for this production', 
                null=True, 
                on_delete=django.db.models.deletion.PROTECT, 
                related_name='productions', 
                to='tenants.site'
            ),
        ),
        
        # Step 4: Fix the batch foreign key reference (it was referencing production_date)
        migrations.RunSQL(
            sql=[
                # Drop the existing FK constraint on batch
                "ALTER TABLE manufacturing_batch DROP CONSTRAINT IF EXISTS manufacturing_batch_production_id_fkey;",
                "ALTER TABLE manufacturing_batch DROP CONSTRAINT IF EXISTS manufacturing_batch_production_date_fkey;",
                # Update the production column to reference by id instead of date
                # First, create a temporary column for the new FK
                "ALTER TABLE manufacturing_batch ADD COLUMN production_id_new INTEGER;",
                # Copy the ID values
                """UPDATE manufacturing_batch b 
                   SET production_id_new = p.id 
                   FROM manufacturing_production p 
                   WHERE b.production_id::date = p.production_date;""",
                # Drop old column and rename
                "ALTER TABLE manufacturing_batch DROP COLUMN IF EXISTS production_id;",
                "ALTER TABLE manufacturing_batch RENAME COLUMN production_id_new TO production_id;",
                # Add the FK constraint
                """ALTER TABLE manufacturing_batch 
                   ADD CONSTRAINT manufacturing_batch_production_id_fkey 
                   FOREIGN KEY (production_id) REFERENCES manufacturing_production(id) ON DELETE CASCADE;""",
            ],
            reverse_sql=[
                # This is complex to reverse, so just note it
                "SELECT 1;"
            ]
        ),
        
        # Step 5: Update unique_together for Production
        migrations.AlterUniqueTogether(
            name='production',
            unique_together={('site', 'production_date')},
        ),
    ]
