# Generated migration to add is_archived field to Django's Group model
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('foodlinecontrol', '0001_add_deletion_request_model'),
    ]

    # This migration adds is_archived to auth.Group, but since we can't modify
    # another app's model directly in migrations, we use SQL
    operations = [
        migrations.RunSQL(
            # Add is_archived column to auth_group table
            sql='''
                ALTER TABLE auth_group 
                ADD COLUMN IF NOT EXISTS is_archived BOOLEAN NOT NULL DEFAULT FALSE;
                
                CREATE INDEX IF NOT EXISTS auth_group_is_archived_idx 
                ON auth_group(is_archived);
            ''',
            # Reverse SQL to remove the column
            reverse_sql='''
                DROP INDEX IF EXISTS auth_group_is_archived_idx;
                ALTER TABLE auth_group DROP COLUMN IF EXISTS is_archived;
            ''',
        ),
    ]
