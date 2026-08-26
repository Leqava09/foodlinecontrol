"""
Data migration: backfill incident_number for existing Incident rows.

IMPORTANT — before running:
1. Run `python manage.py makemigrations incident_management` first.
   That auto-generates the schema migration that adds the
   `incident_number` field (something like
   `00XX_incident_incident_number.py`).
2. Rename this file so it sorts after that one, e.g.
   `00XY_backfill_incident_numbers.py`, and open it — replace
   'REPLACE_WITH_SCHEMA_MIGRATION_NAME' below with the exact
   migration name Django generated in step 1 (no .py extension).
3. Then run `python manage.py migrate incident_management`.
"""
from django.db import migrations


def backfill_incident_numbers(apps, schema_editor):
    Incident = apps.get_model('incident_management', 'Incident')
    Site = apps.get_model('tenants', 'Site')

    # HQ scope (site is NULL) — its own independent counter
    hq_incidents = Incident.objects.filter(site__isnull=True).order_by('id')
    for i, inc in enumerate(hq_incidents, start=1):
        inc.incident_number = i
        inc.save(update_fields=['incident_number'])

    # Each site — its own independent counter
    for site in Site.objects.all():
        site_incidents = Incident.objects.filter(site=site).order_by('id')
        for i, inc in enumerate(site_incidents, start=1):
            inc.incident_number = i
            inc.save(update_fields=['incident_number'])


def reverse_noop(apps, schema_editor):
    # Nothing to reverse — incident_number is left in place (harmless)
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('incident_management', 'REPLACE_WITH_SCHEMA_MIGRATION_NAME'),
    ]

    operations = [
        migrations.RunPython(backfill_incident_numbers, reverse_noop),
    ]
