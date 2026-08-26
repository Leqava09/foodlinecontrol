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
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('incident_management', '0004_incident_incident_number'),
    ]

    operations = [
        migrations.RunPython(backfill_incident_numbers, reverse_noop),
    ]
