from django.db import models
from django.core.validators import FileExtensionValidator
from manufacturing.models import Production, Batch

class Incident(models.Model):
    site = models.ForeignKey(
        'tenants.Site',
        on_delete=models.CASCADE,
        related_name='incidents',
        null=True,
        blank=True,
        help_text="Site this incident belongs to"
    )
    
    # Import tracking fields for HQ incidents
    import_source_site = models.ForeignKey(
        'tenants.Site',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='imported_incidents',
        verbose_name="Import Source Site",
        help_text="Site from which this incident was imported (HQ only)"
    )
    import_source_incident = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='hq_imports',
        verbose_name="Source Incident",
        help_text="Original incident from site (HQ only)"
    )
    
    production_date = models.DateField(
        verbose_name="Production Date",
        null=True,
        blank=True,
    )
    production = models.ForeignKey(
        Production,
        on_delete=models.SET_NULL,
        verbose_name="Production",
        null=True,
        blank=True,
        related_name='incidents'
    )
    batch = models.ForeignKey(
        Batch,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="Production Batch",
    )
    incident_date = models.DateField(verbose_name="Date Incident Occurred")
    location = models.CharField(max_length=255, verbose_name="Where Incident Occurred")
    investigation_start = models.DateField(verbose_name="Investigation From Date")
    investigation_end = models.DateField(verbose_name="Investigation To Date")
    report_date = models.DateField(verbose_name="Date Report Done")
    responsible_person = models.CharField(max_length=255, verbose_name="Responsible Person")
    management_person = models.CharField(max_length=255, verbose_name="Management Person Responsible")
    description = models.TextField(verbose_name="Incident Description", blank=True)
    
    incident_report = models.FileField(
        upload_to='incident_reports/', 
        blank=True, null=True, 
        verbose_name="Incident Report (PDF or file)",
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'doc', 'docx', 'xls', 'xlsx', 'jpg', 'jpeg', 'png'])],
    )

    created = models.DateTimeField(auto_now_add=True, verbose_name="Created At")

    is_archived = models.BooleanField(default=False, db_index=True)
    
    class Meta:
        verbose_name = "Incident"
        verbose_name_plural = "Incidents"
        ordering = ['-incident_date', '-created']

    def __str__(self):
        return f"Incident {self.id} ({self.incident_date}) - Batch: {self.batch}"

class IncidentAttachment(models.Model):
    incident = models.ForeignKey(
        Incident, 
        on_delete=models.CASCADE, 
        related_name='attachments'
    )
    file = models.FileField(
        upload_to='incident_evidence/', 
        verbose_name="Attachment (PDF/JPEG)",
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png'])],
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Incident Attachment"
        verbose_name_plural = "Incident Attachments"

    def __str__(self):
        return f"Attachment for Incident {self.incident.id}"
