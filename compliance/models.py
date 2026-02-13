from django.db import models
from smart_selects.db_fields import ChainedForeignKey


# ============ CATEGORY & TITLE MODELS FIRST ============

class PolicyCategory(models.Model):
    site = models.ForeignKey(
        'tenants.Site',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='policy_categories'
    )
    name = models.CharField(max_length=255)

    class Meta:
        verbose_name = "Policy Category"
        verbose_name_plural = "Policy Categories"
        ordering = ['name']

    def __str__(self):
        return self.name


class PolicyTitle(models.Model):
    category = models.ForeignKey(
        PolicyCategory,
        on_delete=models.CASCADE,
        related_name="titles",
        verbose_name="Category",
    )
    name = models.CharField(max_length=255)

    class Meta:
        verbose_name = "Policy Title"
        verbose_name_plural = "Policy Titles"
        ordering = ["category", "name"]
        unique_together = ("category", "name")

    def __str__(self):
        return self.name


class SopsCategory(models.Model):
    site = models.ForeignKey(
        'tenants.Site',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='sops_categories'
    )
    name = models.CharField(max_length=255)

    class Meta:
        verbose_name = "SOP Category"
        verbose_name_plural = "SOP Categories"
        ordering = ['name']

    def __str__(self):
        return self.name


class SopsTitle(models.Model):
    category = models.ForeignKey(
        SopsCategory,
        on_delete=models.CASCADE,
        related_name="titles",
        verbose_name="Category",
    )
    name = models.CharField(max_length=255)

    class Meta:
        verbose_name = "SOP Title"
        verbose_name_plural = "SOP Titles"
        ordering = ["category", "name"]
        unique_together = ("category", "name")

    def __str__(self):
        return self.name


# ============ DOCUMENT MODELS (now can reference the classes above) ============

class FactoryComplianceDocument(models.Model):
    site = models.ForeignKey(
        'tenants.Site',
        on_delete=models.CASCADE,
        related_name='factory_documents',
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=200)
    issue_date = models.DateField()
    expiry_date = models.DateField(null=True, blank=True)
    comments = models.TextField(blank=True)
    
    is_archived = models.BooleanField(default=False, db_index=True)

    def __str__(self):
        return f"{self.title} ({self.issue_date})"

    class Meta:
        verbose_name = "Factory Document"
        verbose_name_plural = "Factory Documents"


class PolicyComplianceDocument(models.Model):
    site = models.ForeignKey(
        'tenants.Site',
        on_delete=models.CASCADE,
        related_name='policy_documents',
        null=True,
        blank=True,
    )
    category = models.ForeignKey(
        PolicyCategory,
        on_delete=models.SET_NULL,  
        related_name="policy_docs",
        verbose_name="Category",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=200)
    issue_date = models.DateField()
    expiry_date = models.DateField(null=True, blank=True)
    comments = models.TextField(blank=True)
    is_archived = models.BooleanField(default=False, db_index=True)

    def __str__(self):
        cat = self.category.name if self.category else "No Category"
        return f"{cat} – {self.title}"

    class Meta:
        verbose_name = "Policy Document"
        verbose_name_plural = "Policy Documents"
        unique_together = ('category', 'title')

    @property
    def main_file_url(self):
        attachment = self.attachments.first()
        if attachment and attachment.file:
            return attachment.file.url
        return ""

class ProductComplianceDocument(models.Model):
    site = models.ForeignKey(
        'tenants.Site',
        on_delete=models.CASCADE,
        related_name='product_documents',
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=200)
    issue_date = models.DateField()
    expiry_date = models.DateField(null=True, blank=True)
    comments = models.TextField(blank=True)
    is_archived = models.BooleanField(default=False, db_index=True)

    def __str__(self):
        return f"{self.title} ({self.issue_date})"

    class Meta:
        verbose_name = "Product Document"
        verbose_name_plural = "Product Documents"


class SpecSheet(models.Model):
    site = models.ForeignKey(
        'tenants.Site',
        on_delete=models.CASCADE,
        related_name='spec_sheets',
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=200)
    issue_date = models.DateField()
    expiry_date = models.DateField(null=True, blank=True)
    comments = models.TextField(blank=True)
    is_archived = models.BooleanField(default=False, db_index=True)

    def __str__(self):
        return f"{self.title} ({self.issue_date})"

    class Meta:
        verbose_name = "Spec Sheet"
        verbose_name_plural = "Spec Sheets"


class ReportSheet(models.Model):
    site = models.ForeignKey(
        'tenants.Site',
        on_delete=models.CASCADE,
        related_name='report_sheets',
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=200)
    issue_date = models.DateField()
    expiry_date = models.DateField(null=True, blank=True)
    comments = models.TextField(blank=True)
    is_archived = models.BooleanField(default=False, db_index=True)

    def __str__(self):
        return f"{self.title} ({self.issue_date})"

    class Meta:
        verbose_name = "Report Sheet"
        verbose_name_plural = "Report Sheets"


class SopsComplianceDocument(models.Model):
    site = models.ForeignKey(
        'tenants.Site',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='sops_compliance_documents'
    )
    category = models.ForeignKey(
        SopsCategory,
        on_delete=models.SET_NULL, 
        related_name="sops_documents",
        verbose_name="Category",
        null=True,   
        blank=True,  
    )
    title = models.CharField(max_length=200)
    issue_date = models.DateField()
    expiry_date = models.DateField(null=True, blank=True)
    comments = models.TextField(blank=True)
    is_archived = models.BooleanField(default=False, db_index=True)

    def __str__(self):
        cat = self.category.name if self.category else "No Category"
        return f"{cat} – {self.title}"

    class Meta:
        verbose_name = "SOP Document"
        verbose_name_plural = "SOP Documents"
        unique_together = ('category', 'title')

    @property
    def main_file_url(self):
        attachment = self.attachments.first()
        if attachment and attachment.file:
            return attachment.file.url
        return ""

# ============ ATTACHMENT MODELS ============

class FactoryComplianceAttachment(models.Model):
    document = models.ForeignKey(
        FactoryComplianceDocument,
        on_delete=models.CASCADE,
        related_name='attachments'
    )
    file = models.FileField(upload_to='compliance/factory/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Attachment for {self.document.title}"


class PolicyComplianceAttachment(models.Model):
    document = models.ForeignKey(
        PolicyComplianceDocument,
        on_delete=models.CASCADE,
        related_name='attachments'
    )
    file = models.FileField(upload_to='compliance/policy/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Attachment for {self.document.title}"


class ProductComplianceAttachment(models.Model):
    document = models.ForeignKey(
        ProductComplianceDocument,
        on_delete=models.CASCADE,
        related_name='attachments'
    )
    file = models.FileField(upload_to='compliance/product/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Attachment for {self.document.title}"


class SpecSheetAttachment(models.Model):
    document = models.ForeignKey(
        SpecSheet,
        on_delete=models.CASCADE,
        related_name='attachments'
    )
    file = models.FileField(upload_to='compliance/spec_sheets/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Attachment for {self.document.title}"


class ReportSheetAttachment(models.Model):
    document = models.ForeignKey(
        ReportSheet,
        on_delete=models.CASCADE,
        related_name='attachments'
    )
    file = models.FileField(upload_to='compliance/report_sheets/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Attachment for {self.document.title}"


class SopsComplianceAttachment(models.Model):
    document = models.ForeignKey(
        SopsComplianceDocument,
        on_delete=models.CASCADE,
        related_name='attachments'
    )
    file = models.FileField(upload_to='compliance/sops/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Attachment for {self.document.title}"
