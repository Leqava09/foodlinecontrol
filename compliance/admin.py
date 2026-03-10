from django.contrib import admin
from django.utils.html import format_html, format_html_join, mark_safe
from .models import (
    FactoryComplianceDocument, FactoryComplianceAttachment,
    PolicyComplianceDocument, PolicyComplianceAttachment,
    ProductComplianceDocument, ProductComplianceAttachment,
    SopsComplianceDocument, SopsComplianceAttachment, PolicyCategory, SopsCategory,
    SpecSheet, SpecSheetAttachment,
    ReportSheet, ReportSheetAttachment,
)
from .forms import (
    FactoryComplianceForm,
    PolicyComplianceForm,
    ProductComplianceForm,
    SopsComplianceForm,
    SpecSheetForm,
    ReportSheetForm,
)

from django.utils.formats import date_format
from foodlinecontrol.admin_base import ArchivableAdmin
from tenants.admin_utils import SiteAwareModelAdmin

class GenericAttachmentInline(admin.TabularInline):
    extra = 1
    fields = ['file', 'uploaded_at_display']
    readonly_fields = ['uploaded_at_display']

    def uploaded_at_display(self, obj):
        if not obj.uploaded_at:
            return "-"
        return date_format(obj.uploaded_at, "d-m-Y H:i")
    uploaded_at_display.short_description = "Uploaded at"

# FACTORY
class FactoryComplianceAttachmentInline(GenericAttachmentInline):
    model = FactoryComplianceAttachment

@admin.register(FactoryComplianceDocument)
class FactoryComplianceDocumentAdmin(SiteAwareModelAdmin, ArchivableAdmin):
    form = FactoryComplianceForm
    inlines = [FactoryComplianceAttachmentInline]
    list_display = ['title', 'issue_date', 'expiry_date', 'attachment_links']
    search_fields = ['title', 'comments']
    def attachment_links(self, obj):
        links = format_html_join(mark_safe('<br>'), '<a href="{}" target="_blank">{}</a>', ((a.file.url, a.file.name.split('/')[-1]) for a in obj.attachments.all()))
        return links or '-'
    attachment_links.short_description = "Attachments"

# POLICY
class PolicyComplianceAttachmentInline(GenericAttachmentInline):
    model = PolicyComplianceAttachment

@admin.register(PolicyComplianceDocument)
class PolicyComplianceDocumentAdmin(SiteAwareModelAdmin, ArchivableAdmin):
    form = PolicyComplianceForm
    inlines = [PolicyComplianceAttachmentInline]
    list_display = ['title', 'category', 'issue_date', 'expiry_date', 'attachment_links']
    list_filter = ['category']
    search_fields = ['title', 'comments', 'category__name']

    class Media:
        js = ('js/compliance_category_edit_icons.js',)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter category dropdown to show only categories matching the document's site"""
        if db_field.name == 'category':
            current_site = getattr(request, 'current_site', None)
            if current_site:
                # Site admin: show only categories for this site
                kwargs['queryset'] = PolicyCategory.objects.filter(site=current_site)
            else:
                # HQ admin: show only HQ categories (site=NULL)
                kwargs['queryset'] = PolicyCategory.objects.filter(site__isnull=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def attachment_links(self, obj):
        links = format_html_join(mark_safe('<br>'), '<a href="{}" target="_blank">{}</a>', ((a.file.url, a.file.name.split('/')[-1]) for a in obj.attachments.all()))
        return links or '-'
    attachment_links.short_description = "Attachments"


# PRODUCT
class ProductComplianceAttachmentInline(GenericAttachmentInline):
    model = ProductComplianceAttachment

@admin.register(ProductComplianceDocument)
class ProductComplianceDocumentAdmin(SiteAwareModelAdmin, ArchivableAdmin):
    form = ProductComplianceForm
    inlines = [ProductComplianceAttachmentInline]
    list_display = ['title', 'issue_date', 'expiry_date', 'attachment_links']
    search_fields = ['title', 'comments']
    def attachment_links(self, obj):
        links = format_html_join(mark_safe('<br>'), '<a href="{}" target="_blank">{}</a>', ((a.file.url, a.file.name.split('/')[-1]) for a in obj.attachments.all()))
        return links or '-'
    attachment_links.short_description = "Attachments"

# SOPS
class SopsComplianceAttachmentInline(GenericAttachmentInline):
    model = SopsComplianceAttachment

@admin.register(SopsComplianceDocument)
class SopsComplianceDocumentAdmin(SiteAwareModelAdmin, ArchivableAdmin):
    form = SopsComplianceForm
    inlines = [SopsComplianceAttachmentInline]
    list_display = ['title', 'category', 'issue_date', 'expiry_date', 'attachment_links']
    list_filter = ['category']
    search_fields = ['title', 'comments', 'category__name']

    class Media:
        js = ('js/compliance_category_edit_icons.js',)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter category dropdown to show only categories matching the document's site"""
        if db_field.name == 'category':
            current_site = getattr(request, 'current_site', None)
            if current_site:
                # Site admin: show only categories for this site
                kwargs['queryset'] = SopsCategory.objects.filter(site=current_site)
            else:
                # HQ admin: show only HQ categories (site=NULL)
                kwargs['queryset'] = SopsCategory.objects.filter(site__isnull=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def attachment_links(self, obj):
        links = format_html_join(mark_safe('<br>'), '<a href="{}" target="_blank">{}</a>', ((a.file.url, a.file.name.split('/')[-1]) for a in obj.attachments.all()))
        return links or '-'
    attachment_links.short_description = "Attachments"

# SPEC SHEETS
class SpecSheetAttachmentInline(admin.TabularInline):
    model = SpecSheetAttachment
    extra = 1

@admin.register(SpecSheet)
class SpecSheetAdmin(SiteAwareModelAdmin, ArchivableAdmin):
    form = SpecSheetForm
    inlines = [SpecSheetAttachmentInline]
    list_display = ['title', 'issue_date', 'expiry_date', 'attachment_links']
    search_fields = ['title', 'comments']
    def attachment_links(self, obj):
        links = format_html_join(mark_safe('<br>'), '<a href="{}" target="_blank">{}</a>', ((a.file.url, a.file.name.split('/')[-1]) for a in obj.attachments.all()))
        return links or '-'
    attachment_links.short_description = "Attachments"
# REPORT SHEETS
class ReportSheetAttachmentInline(admin.TabularInline):
    model = ReportSheetAttachment
    extra = 1

@admin.register(ReportSheet)
class ReportSheetAdmin(SiteAwareModelAdmin, ArchivableAdmin):
    form = ReportSheetForm
    inlines = [ReportSheetAttachmentInline]
    list_display = ['title', 'issue_date', 'expiry_date', 'attachment_links']
    search_fields = ['title', 'comments']
    def attachment_links(self, obj):
        links = format_html_join(mark_safe('<br>'), '<a href="{}" target="_blank">{}</a>', ((a.file.url, a.file.name.split('/')[-1]) for a in obj.attachments.all()))
        return links or '-'
    attachment_links.short_description = "Attachments"


@admin.register(PolicyCategory)
class PolicyCategoryAdmin(SiteAwareModelAdmin, admin.ModelAdmin):
    list_display = ['name']
    search_fields = ['name']
    
    def get_exclude(self, request, obj=None):
        """Hide site field - auto-assigned by SiteAwareModelAdmin"""
        exclude = list(super().get_exclude(request, obj) or [])
        if 'site' not in exclude:
            exclude.append('site')
        return exclude
    
    def get_model_perms(self, request):
        """Hide from admin index/dashboard"""
        return {}


@admin.register(SopsCategory)
class SopsCategoryAdmin(SiteAwareModelAdmin, admin.ModelAdmin):
    list_display = ['name']
    search_fields = ['name']
    
    def get_exclude(self, request, obj=None):
        """Hide site field - auto-assigned by SiteAwareModelAdmin"""
        exclude = list(super().get_exclude(request, obj) or [])
        if 'site' not in exclude:
            exclude.append('site')
        return exclude
    
    def get_model_perms(self, request):
        """Hide from admin index/dashboard"""
        return {}
