from django.contrib import admin
from django.utils.html import format_html
from .models import Person, Training, Induction, Leave, Department, PositionLevel
import nested_admin
import logging

logger = logging.getLogger(__name__)
from django.utils.formats import date_format
from django.contrib import admin
from django.utils.html import format_html
from .models import Person, Training, Induction, Leave, Department, PositionLevel
from .forms import (
    PersonAdminForm,
    TrainingInlineForm,
    InductionInlineForm,
    LeaveInlineForm,
)
from compliance.models import PolicyComplianceDocument, SopsComplianceDocument
from foodlinecontrol.admin_base import ArchivableAdmin
from tenants.admin_utils import SiteAwareModelAdmin

@admin.register(Department)
class DepartmentAdmin(SiteAwareModelAdmin):
    list_display = ['name']                 
    search_fields = ['name']              
    exclude_site_from_form = True  # Auto-assign site, hide from form
    
    def get_model_perms(self, request):
        """Hide from admin index/dashboard"""
        return {}
    
@admin.register(PositionLevel)
class PositionLevelAdmin(SiteAwareModelAdmin):
    list_display = ['name']                  
    search_fields = ['name']
    exclude_site_from_form = True  # Auto-assign site, hide from form
    
    def get_model_perms(self, request):
        """Hide from admin index/dashboard"""
        return {}
        
class TrainingInline(admin.StackedInline):
    model = Training
    form = TrainingInlineForm
    extra = 0
    fieldsets = (
        (None, {
            "fields": (
                ("training_date", "next_review_date"),
                "training_provided",
                ("policy_category", "linked_policy"),
                ("sop_category", "linked_sop"),
                "trainer",
                "document",
                "notes",
            ),
        }),
    )
    can_delete = True

    def get_formset(self, request, obj=None, **kwargs):
        # keep current Person object on the request for use below
        request._person_obj = obj
        return super().get_formset(request, obj, **kwargs)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Filter policy_category and sop_category by site
        if db_field.name == "policy_category":
            from compliance.models import PolicyCategory
            # First try to get site from person object
            person_obj = getattr(request, "_person_obj", None)
            site_id = None
            
            # DEBUG LOGGING
            logger.debug(
                "Training policy category filtering: person=%s, has_current_site=%s, has_site_slug=%s",
                person_obj,
                hasattr(request, 'current_site'),
                hasattr(request, '_site_slug'),
            )
            
            # Check if person has a site assigned (access site object explicitly)
            if person_obj and hasattr(person_obj, 'site') and person_obj.site is not None:
                site_id = person_obj.site.id
                logger.debug("Using person's site_id: %s", site_id)
            # Fall back to middleware-set current_site
            elif hasattr(request, 'current_site') and request.current_site:
                site_id = request.current_site.id
                logger.debug("Using request.current_site: %s (id: %s)", request.current_site.name, site_id)
            
            # Filter by site if found
            if site_id:
                kwargs["queryset"] = PolicyCategory.objects.filter(site_id=site_id)
                logger.debug("Filtered to site %s: %s", site_id, list(kwargs['queryset'].values_list('name', flat=True)))
            else:
                logger.debug("No site found - showing all")
        
        elif db_field.name == "sop_category":
            from compliance.models import SopsCategory
            # First try to get site from person object
            person_obj = getattr(request, "_person_obj", None)
            site_id = None
            
            # Check if person has a site assigned (access site object explicitly)
            if person_obj and hasattr(person_obj, 'site') and person_obj.site is not None:
                site_id = person_obj.site.id
            # Fall back to middleware-set current_site
            elif hasattr(request, 'current_site') and request.current_site:
                site_id = request.current_site.id
            
            # Filter by site if found
            if site_id:
                kwargs["queryset"] = SopsCategory.objects.filter(site_id=site_id)
        
        elif db_field.name == "linked_policy":
            qs = PolicyComplianceDocument.objects.filter(
                attachments__isnull=False
            ).distinct()

            # If editing an existing Induction instance
            induction_obj = getattr(request, "_induction_obj", None)
            if induction_obj and induction_obj.policy_category_id:
                qs = qs.filter(category_id=induction_obj.policy_category_id)

            kwargs["queryset"] = qs

        elif db_field.name == "linked_sop":
            qs = SopsComplianceDocument.objects.filter(
                attachments__isnull=False
            ).distinct()
            induction_obj = getattr(request, "_induction_obj", None)
            if induction_obj and induction_obj.sop_category_id:
                qs = qs.filter(category_id=induction_obj.sop_category_id)
            kwargs["queryset"] = qs

        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class InductionInline(admin.StackedInline):
    model = Induction
    form = InductionInlineForm
    extra = 0
    fieldsets = (
        (None, {
            "fields": (
                ("induction_date", "next_review_date"),
                "induction_provided",
                ("policy_category", "linked_policy"),
                ("sop_category", "linked_sop"),
                "facilitator",    
                "document",
                "notes",
            ),
        }),
    )
    can_delete = True
    
    def get_formset(self, request, obj=None, **kwargs):
        # keep current Person object on the request for use below
        request._person_obj = obj
        return super().get_formset(request, obj, **kwargs)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Filter policy_category and sop_category by site
        if db_field.name == "policy_category":
            from compliance.models import PolicyCategory
            # First try to get site from person object
            person_obj = getattr(request, "_person_obj", None)
            site_id = None
            
            # Check if person has a site assigned (access site object explicitly)
            if person_obj and hasattr(person_obj, 'site') and person_obj.site is not None:
                site_id = person_obj.site.id
            # Fall back to middleware-set current_site
            elif hasattr(request, 'current_site') and request.current_site:
                site_id = request.current_site.id
            
            # Filter by site if found
            if site_id:
                kwargs["queryset"] = PolicyCategory.objects.filter(site_id=site_id)
        
        elif db_field.name == "sop_category":
            from compliance.models import SopsCategory
            # First try to get site from person object
            person_obj = getattr(request, "_person_obj", None)
            site_id = None
            
            # Check if person has a site assigned (access site object explicitly)
            if person_obj and hasattr(person_obj, 'site') and person_obj.site is not None:
                site_id = person_obj.site.id
            # Fall back to middleware-set current_site
            elif hasattr(request, 'current_site') and request.current_site:
                site_id = request.current_site.id
            
            # Filter by site if found
            if site_id:
                kwargs["queryset"] = SopsCategory.objects.filter(site_id=site_id)
        
        elif db_field.name == "linked_policy":
            qs = PolicyComplianceDocument.objects.filter(
                attachments__isnull=False
            ).distinct()

            # If editing an existing Induction instance
            induction_obj = getattr(request, "_induction_obj", None)
            if induction_obj and induction_obj.policy_category_id:
                qs = qs.filter(category_id=induction_obj.policy_category_id)

            kwargs["queryset"] = qs

        elif db_field.name == "linked_sop":
            qs = SopsComplianceDocument.objects.filter(
                attachments__isnull=False
            ).distinct()
            induction_obj = getattr(request, "_induction_obj", None)
            if induction_obj and induction_obj.sop_category_id:
                qs = qs.filter(category_id=induction_obj.sop_category_id)
            kwargs["queryset"] = qs

        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class LeaveInline(admin.StackedInline):
    model = Leave
    form = LeaveInlineForm
    extra = 0
    fieldsets = (
        (None, {
            "fields": (
                ("leave_type", "start_date", "end_date", "days"),
            ),
        }),
        ("Details", {
            "fields": (
                ("reason", "status"),
                ("approved_by", "document"),
            ),
        }),
    )
    readonly_fields = ()
    can_delete = True

@admin.register(Person)
class PersonAdmin(SiteAwareModelAdmin, ArchivableAdmin):
    form = PersonAdminForm

    list_display = (
        'employee_id',
        'full_name',
        'department',
        'position_level',
        'position',
        'status_badge',
        'hire_date',
    )

    list_filter = ('status', 'department', 'position_level', 'hire_date')
    search_fields = ('first_name', 'last_name', 'employee_id', 'email')

    # Use display methods, not raw fields
    readonly_fields = ('created_at_display', 'updated_at_display')

    fieldsets = (
        ('Personal Information', {
            'fields': (
                ('employee_id'),
                ('first_name', 'last_name'),         
                ('email', 'phone'),  
            )
        }),
        ('Employment Details', {
            'fields': (
                ('department', 'position_level'),     # row 1
                ('position', 'hire_date', 'status'),  # row 2
            )
        }),
        ('Timestamps', {
            'fields': (
                ('created_at_display', 'updated_at_display'),
            ),
            'classes': ('collapse',),
        }),
    )

    inlines = [InductionInline, TrainingInline, LeaveInline]

    class Media:
        js = (
            'js/hr_grappelli_datepicker.js',
            'js/hr_view_docs.js',
            'js/hr_auto_expand_inlines.js',
        )

    # ---- helper methods ----
    def full_name(self, obj):
        if obj.last_name:
            return f"{obj.first_name} {obj.last_name}"
        return obj.first_name
    full_name.short_description = "Name"

    def status_badge(self, obj):
        colors = {
            'active': '#28a745',
            'inactive': '#ffc107',
            'suspended': '#dc3545',
            'left': '#6c757d',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = "Status"

    def created_at_display(self, obj):
        if not obj.created_at:
            return "-"
        return date_format(obj.created_at, "d-m-Y H:i")
    created_at_display.short_description = "Created at"
    created_at_display.admin_order_field = "created_at"

    def updated_at_display(self, obj):
        if not obj.updated_at:
            return "-"
        return date_format(obj.updated_at, "d-m-Y H:i")
    updated_at_display.short_description = "Updated at"
    updated_at_display.admin_order_field = "updated_at"
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Filter department and position_level by site
        if db_field.name == "department":
            # Use middleware-set current_site
            if hasattr(request, 'current_site') and request.current_site:
                kwargs["queryset"] = Department.objects.filter(site=request.current_site)
        
        elif db_field.name == "position_level":
            # Use middleware-set current_site
            if hasattr(request, 'current_site') and request.current_site:
                kwargs["queryset"] = PositionLevel.objects.filter(site=request.current_site)
        
        formfield = super().formfield_for_foreignkey(db_field, request, **kwargs)

        if db_field.name in ("linked_policy", "linked_sop") and formfield.choices:
            new_choices = []
            for value, label in formfield.choices:
                if value:
                    if db_field.name == "linked_policy":
                        doc = PolicyComplianceDocument.objects.get(pk=value)
                    else:
                        doc = SopsComplianceDocument.objects.get(pk=value)
                    html_label = format_html(
                        '<span data-doc-url="{}">{}</span>',
                        doc.main_file_url,
                        label,
                    )
                    new_choices.append((value, html_label))
                else:
                    new_choices.append((value, label))
            formfield.choices = new_choices

        return formfield
