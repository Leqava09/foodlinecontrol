"""
HQ Admin Site - Separate Django admin for HQ-level management.

This admin site is accessed at /hq/admin/ and ONLY contains:
- Sites management
- User Site Assignments

Site-level apps (Inventory, Manufacturing, etc.) are NOT registered here.
"""
from django.contrib import admin
from django.contrib.admin import AdminSite
from django import forms
from django.utils.html import mark_safe, format_html
from django.shortcuts import render, redirect
from django.urls import path
from django.contrib import messages
from foodlinecontrol.admin_base import ArchivableAdmin, ArchivedToggleFilter


class HQAdminSite(AdminSite):
    """
    Custom AdminSite for HQ-level management.
    
    URL: /hq/admin/
    Contains: Sites, User Site Assignments
    """
    site_header = "🏢 FoodLineControl HQ Admin"
    site_title = "HQ Admin"
    index_title = "HQ Management"
    site_url = "/hq/"  # "View site" links to HQ home instead of site
    
    # Custom templates
    index_template = "hq_admin/index.html"
    app_index_template = "hq_admin/app_index.html"
    
    def has_permission(self, request):
        """Only allow HQ users (superusers or users with is_hq_user flag)"""
        if not request.user.is_active:
            return False
        if request.user.is_superuser:
            return True
        try:
            return request.user.site_profile.is_hq_user
        except:
            return False
    
    def each_context(self, request):
        """Add HQ-specific context to all admin pages"""
        context = super().each_context(request)
        context['is_hq_admin'] = True
        context['hq_home_url'] = '/hq/'
        return context
    
    def get_urls(self):
        """Override to use custom logout that redirects to HQ login"""
        from django.urls import path
        from foodlinecontrol.views import custom_logout
        
        urls = super().get_urls()
        # Replace the default logout URL with our custom logout
        custom_urls = [
            path('logout/', custom_logout, name='logout'),
        ]
        return custom_urls + urls


# Create the HQ admin site instance
hq_admin_site = HQAdminSite(name='hq_admin')


# Import models here to avoid circular imports
from .models import Site, UserSite


# Custom filter for Site archived status
class SiteArchivedFilter(admin.SimpleListFilter):
    title = "Status"
    parameter_name = "is_archived"

    def lookups(self, request, model_admin):
        return (
            ("0", "Active"),
            ("1", "Archived"),
            ("all", "All"),
        )

    def queryset(self, request, queryset):
        return queryset


class HQSiteAdmin(admin.ModelAdmin):
    """
    Admin for Sites - registered ONLY in HQ Admin.
    Uses is_archived field to archive/restore sites.
    """
    change_list_template = "admin/archivable_change_list.html"
    actions = ["archive_sites", "restore_sites"]
    list_display = ('display_name', 'data_summary', 'admin_link', 'is_active', 'created_on')
    list_filter = (SiteArchivedFilter, 'created_on')
    search_fields = ('name',)
    readonly_fields = ('created_on', 'updated_on')
    
    fieldsets = (
        ('Site Information', {
            'fields': ('name', 'description', 'is_active'),
            'description': 'Basic information about this manufacturing site.'
        }),
        ('Admin Appearance', {
            'fields': ('admin_background',),
            'description': 'Upload a JPEG/PNG image to display as background on the admin dashboard for this site.'
        }),
        ('Timestamps', {
            'fields': ('created_on', 'updated_on'),
            'classes': ('collapse',)
        }),
    )
    
    # Archive/Restore actions
    def archive_sites(self, request, queryset):
        updated = queryset.update(is_archived=True)
        self.message_user(request, f"{updated} site(s) archived.")
    archive_sites.short_description = "Archive selected sites"

    def restore_sites(self, request, queryset):
        updated = queryset.update(is_archived=False)
        self.message_user(request, f"{updated} site(s) restored.")
    restore_sites.short_description = "Restore selected sites"

    def get_actions(self, request):
        """Conditionally show archive/restore actions based on filter"""
        actions = super().get_actions(request)
        flag = request.GET.get("is_archived")
        
        # If showing only active sites, hide restore action
        if flag in (None, "", "0"):
            actions.pop("restore_sites", None)
        # If showing only archived sites, hide archive action
        if flag == "1":
            actions.pop("archive_sites", None)
        
        return actions

    def get_queryset(self, request):
        """Filter sites based on archived status"""
        qs = super().get_queryset(request)
        
        flag = request.GET.get("is_archived")
        if flag == "1":
            # Show archived sites
            qs = qs.filter(is_archived=True)
        elif flag == "0":
            # Show active sites
            qs = qs.filter(is_archived=False)
        elif flag == "all":
            # Show all sites
            pass
        else:
            # Default: show only active sites
            qs = qs.filter(is_archived=False)
        
        return qs
    
    def get_urls(self):
        """Add custom URL for site deletion with data options"""
        urls = super().get_urls()
        custom_urls = [
            path('<int:site_id>/delete-with-options/',
                 self.admin_site.admin_view(self.delete_with_options_view),
                 name='tenants_site_delete_with_options'),
        ]
        return custom_urls + urls
    
    def delete_with_options_view(self, request, site_id):
        """Custom view for site deletion with data retention options"""
        site = Site.objects.get(pk=site_id)
        
        # Count related data
        data_counts = self._get_site_data_counts(site)
        total_records = sum(data_counts.values())
        
        if request.method == 'POST':
            action = request.POST.get('action')
            
            if action == 'delete_all':
                # Delete site and all its data (CASCADE handles this)
                site_name = site.name
                site.delete()
                messages.success(request, f"Site '{site_name}' and all its data ({total_records} records) have been deleted.")
                return redirect('hq_admin:tenants_site_changelist')
                
            elif action == 'keep_data':
                # Just deactivate the site, keep data orphaned (set site=NULL)
                from manufacturing.models import Production, Batch
                from inventory.models import StockItem, PurchaseOrder
                from commercial.models import Supplier, Client, Warehouse, Transporter
                from costing.models import OverheadCosting, SalaryCosting, ProductCosting, BillingDocumentHeader
                from incident_management.models import Incident
                from human_resources.models import Person
                from transport.models import TransportLoad, DeliverySite
                
                # Orphan all related data (set site=NULL)
                models_with_site = [
                    Production, Batch, StockItem, PurchaseOrder,
                    Supplier, Client, Warehouse, Transporter,
                    OverheadCosting, SalaryCosting, ProductCosting, BillingDocumentHeader,
                    Incident, Person, TransportLoad, DeliverySite
                ]
                
                for model in models_with_site:
                    if hasattr(model, 'site'):
                        model.objects.filter(site=site).update(site=None)
                
                site_name = site.name
                site.delete()
                messages.success(request, f"Site '{site_name}' deleted. Its data ({total_records} records) has been preserved as HQ data.")
                return redirect('hq_admin:tenants_site_changelist')
            
            elif action == 'cancel':
                return redirect('hq_admin:tenants_site_change', site_id)
        
        context = {
            'site': site,
            'data_counts': data_counts,
            'total_records': total_records,
            'title': f'Delete Site: {site.name}',
            'opts': self.model._meta,
        }
        return render(request, 'admin/tenants/site/delete_with_options.html', context)
    
    def _get_site_data_counts(self, site):
        """Count all data records for this site"""
        from manufacturing.models import Production, Batch
        from inventory.models import StockItem, PurchaseOrder
        from commercial.models import Supplier, Client, Warehouse, Transporter
        from costing.models import OverheadCosting, SalaryCosting, ProductCosting, BillingDocumentHeader
        from incident_management.models import Incident
        from human_resources.models import Person
        from transport.models import TransportLoad, DeliverySite
        
        counts = {
            'Productions': Production.objects.filter(site=site).count(),
            'Batches': Batch.objects.filter(site=site).count(),
            'Stock Items': StockItem.objects.filter(site=site).count(),
            'Purchase Orders': PurchaseOrder.objects.filter(site=site).count(),
            'Suppliers': Supplier.objects.filter(site=site).count(),
            'Clients': Client.objects.filter(site=site).count(),
            'Warehouses': Warehouse.objects.filter(site=site).count(),
            'Transporters': Transporter.objects.filter(site=site).count(),
            'Overhead Costings': OverheadCosting.objects.filter(site=site).count(),
            'Salary Costings': SalaryCosting.objects.filter(site=site).count(),
            'Product Costings': ProductCosting.objects.filter(site=site).count(),
            'Billing Documents': BillingDocumentHeader.objects.filter(site=site).count(),
            'Incidents': Incident.objects.filter(site=site).count(),
            'Staff': Person.objects.filter(site=site).count(),
            'Transport Loads': TransportLoad.objects.filter(site=site).count(),
            'Delivery Sites': DeliverySite.objects.filter(site=site).count(),
        }
        return {k: v for k, v in counts.items() if v > 0}  # Only return non-zero counts
    
    def data_summary(self, obj):
        """Display count of data records for this site"""
        counts = self._get_site_data_counts(obj)
        total = sum(counts.values())
        if total == 0:
            return mark_safe('<span style="color:#999;">No data</span>')
        return mark_safe(f'<span title="{", ".join(f"{k}: {v}" for k, v in counts.items())}">{total} records</span>')
    data_summary.short_description = 'Data'
    
    def display_name(self, obj):
        """Display site name with status indicator"""
        status = '✅' if obj.is_active else '⏸️'
        return mark_safe(f'{status} {obj.name}')
    display_name.short_description = 'Site Name'
    
    def admin_link(self, obj):
        """Display link to site admin"""
        url = obj.get_admin_url()
        return mark_safe(f'<a href="{url}" class="button" style="padding: 5px 10px;">Open Site Admin →</a>')
    admin_link.short_description = 'Access'
    
    def delete_model(self, request, obj):
        """Override to redirect to custom delete view"""
        # Redirect to custom delete view with options
        from django.http import HttpResponseRedirect
        return HttpResponseRedirect(f'{obj.pk}/delete-with-options/')
    
    def response_delete(self, request, obj_display, obj_id):
        """Redirect single delete to custom view"""
        from django.http import HttpResponseRedirect
        return HttpResponseRedirect(f'{obj_id}/delete-with-options/')


class HQUserSiteAdmin(ArchivableAdmin):
    """
    Admin for HQ Users - registered ONLY in HQ Admin.
    Simple interface: just hq_username and hq_password.
    All HQ users have access to all sites automatically.
    """
    list_display = ('hq_username_display', 'created_on', 'updated_on')
    list_filter = (ArchivedToggleFilter, 'created_on')
    search_fields = ('hq_username',)
    readonly_fields = ('created_on', 'updated_on')
    
    fieldsets = (
        ('HQ Credentials', {
            'fields': ('hq_username', 'hq_password'),
            'description': 'HQ login credentials. Hq_username must be unique. Password will be encrypted with PBKDF2.'
        }),
        ('Timestamps', {
            'fields': ('created_on', 'updated_on'),
            'classes': ('collapse',)
        }),
    )
    
    def hq_username_display(self, obj):
        """Display HQ username"""
        return mark_safe(f'👤 {obj.hq_username}') if obj.hq_username else '(no username)'
    hq_username_display.short_description = 'HQ Username'
    
    def get_queryset(self, request):
        """
        Show HQ users (is_hq_user=True) everywhere.
        In site-specific admin context, also show that site's assigned users.
        """
        from django.db.models import Q
        
        # Get base queryset
        qs = super().get_queryset(request)
        
        # Always show HQ users
        hq_users = qs.filter(is_hq_user=True)
        
        # If in site admin context, also show users assigned to that site
        site_id = request.session.get('current_site_id')
        if site_id:
            # Site-specific users for current site + HQ users
            site_users = qs.filter(assigned_site_id=site_id, is_archived=False)
            qs = hq_users | site_users
        else:
            # HQ context - show only HQ users
            qs = hq_users
        
        return qs.distinct()


# ============================================================================
# HQ-SPECIFIC WRAPPER ADMINS - Filter by site=NULL (HQ-only data)
# ============================================================================

# Commercial Models - HQ data only (site=NULL)
from commercial.models import Client, CompanyDetails, Transporter, Warehouse
from commercial.admin import ClientAdmin, CompanyDetailsAdmin, TransporterAdmin, WarehouseAdmin

class HQClientAdmin(ClientAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).filter(site__isnull=True)

class HQCompanyDetailsAdmin(CompanyDetailsAdmin):
    """Company Details admin for HQ - includes admin background setting"""
    
    list_display = ["name", "vat_number", "is_active"]  # Exclude 'site' column for HQ
    
    fieldsets = (
        ("Identity", {
            "fields": (
                "name",
                "legal_name",
                "registration_number",
                "vat_number",
                "logo",
            )
        }),
        ("Contact details", {
            "fields": (
                "address_line1",
                "address_line2",
                "city",
                "province",
                "postal_code",
                "country",
                "phone",
                "email",
                "website",
            )
        }),
        ("Banking details", {
            "fields": (
                "bank_name",
                "bank_account_name",
                "bank_account_number",
                "bank_branch_code",
            )
        }),
        ("Document templates", {
            "fields": (
                "currency",
                "billing_template",
                "po_template",
            )
        }),
        ("Admin Appearance", {
            "fields": ("admin_background",),
            "description": "Upload a JPEG/PNG image to display as background on the HQ admin dashboard."
        }),
        ("Status", {
            "fields": ("is_active",),
        }),
    )
    
    def get_list_display(self, request):
        """Override to prevent 'site' column from being added"""
        return self.list_display
    
    def get_queryset(self, request):
        return super().get_queryset(request).filter(site__isnull=True)

class HQTransporterAdmin(TransporterAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).filter(site__isnull=True)
    
    def get_exclude(self, request, obj=None):
        """Hide site field from form - transporters are HQ-only"""
        exclude = list(super().get_exclude(request, obj) or [])
        if 'site' not in exclude:
            exclude.append('site')
        return exclude

class HQWarehouseAdmin(WarehouseAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).filter(site__isnull=True)

# Compliance Models - HQ data only (site=NULL for master records)
from compliance.models import PolicyComplianceDocument, ProductComplianceDocument, SopsComplianceDocument, SpecSheet, PolicyCategory, SopsCategory
from compliance.admin import PolicyComplianceDocumentAdmin, ProductComplianceDocumentAdmin, SopsComplianceDocumentAdmin, SpecSheetAdmin

class HQPolicyComplianceDocumentAdmin(PolicyComplianceDocumentAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).filter(site__isnull=True)
    
    def get_exclude(self, request, obj=None):
        """Hide site field in HQ admin"""
        excluded = list(super().get_exclude(request, obj) or [])
        if 'site' not in excluded:
            excluded.append('site')
        return excluded
    
    def save_model(self, request, obj, form, change):
        """Force site=NULL for HQ records"""
        obj.site = None
        super().save_model(request, obj, form, change)

class HQProductComplianceDocumentAdmin(ProductComplianceDocumentAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).filter(site__isnull=True)
    
    def get_exclude(self, request, obj=None):
        """Hide site field in HQ admin"""
        excluded = list(super().get_exclude(request, obj) or [])
        if 'site' not in excluded:
            excluded.append('site')
        return excluded
    
    def save_model(self, request, obj, form, change):
        """Force site=NULL for HQ records"""
        obj.site = None
        super().save_model(request, obj, form, change)

class HQSopsComplianceDocumentAdmin(SopsComplianceDocumentAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).filter(site__isnull=True)
    
    def get_exclude(self, request, obj=None):
        """Hide site field in HQ admin"""
        excluded = list(super().get_exclude(request, obj) or [])
        if 'site' not in excluded:
            excluded.append('site')
        return excluded
    
    def save_model(self, request, obj, form, change):
        """Force site=NULL for HQ records"""
        obj.site = None
        super().save_model(request, obj, form, change)

class HQSpecSheetAdmin(SpecSheetAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).filter(site__isnull=True)
    
    def get_exclude(self, request, obj=None):
        """Hide site field in HQ admin"""
        excluded = list(super().get_exclude(request, obj) or [])
        if 'site' not in excluded:
            excluded.append('site')
        return excluded
    
    def save_model(self, request, obj, form, change):
        """Force site=NULL for HQ records"""
        obj.site = None
        super().save_model(request, obj, form, change)

# Category Admins - Hidden from sidebar but accessible via related widget
class HQPolicyCategoryAdmin(admin.ModelAdmin):
    list_display = ['name']
    search_fields = ['name']
    exclude = ['site']
    
    def get_model_perms(self, request):
        """Hide from admin index/sidebar"""
        return {}
    
    def get_queryset(self, request):
        """Show only HQ categories (site=NULL)"""
        return super().get_queryset(request).filter(site__isnull=True)
    
    def save_model(self, request, obj, form, change):
        """Force site=NULL for HQ categories"""
        obj.site = None
        super().save_model(request, obj, form, change)

class HQSopsCategoryAdmin(admin.ModelAdmin):
    list_display = ['name']
    search_fields = ['name']
    exclude = ['site']
    
    def get_model_perms(self, request):
        """Hide from admin index/sidebar"""
        return {}
    
    def get_queryset(self, request):
        """Show only HQ categories (site=NULL)"""
        return super().get_queryset(request).filter(site__isnull=True)
    
    def save_model(self, request, obj, form, change):
        """Force site=NULL for HQ categories"""
        obj.site = None
        super().save_model(request, obj, form, change)

# Costing Models - HQ data only (site=NULL)
from costing.models import BillingDocumentHeader, BillingLineItem
from costing.admin import BillingDocumentHeaderAdmin
from costing.forms import ImportBillingForm, HQDirectBillingForm
from django.urls import path
from django.utils.html import mark_safe

# Register Batch for autocomplete in HQ admin
from manufacturing.models import Batch

class HQBatchAdmin(admin.ModelAdmin):
    """HQ Batch admin with search for autocomplete only - HIDDEN from menu"""
    search_fields = ['batch_number', 'product__product_name', 'a_no']
    list_display = ['batch_number', 'product', 'size', 'site']
    list_filter = ['site']
    
    def has_module_permission(self, request):
        """Hide from admin menu - only used for autocomplete"""
        return False
        
    def has_add_permission(self, request):
        return False
        
    def has_change_permission(self, request, obj=None):
        return False
        
    def has_delete_permission(self, request, obj=None):
        return False
    
    def get_queryset(self, request):
        # Show all batches from all sites for HQ
        return Batch.objects.all()
    
    def get_search_results(self, request, queryset, search_term):
        """Filter by site if provided and only return results when searching"""
        # Only return results if there's a search term (don't show all batches)
        if not search_term:
            return queryset.none(), False
        
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        return queryset, use_distinct

# Register with special admin that has NO permissions but allows autocomplete
hq_admin_site.register(Batch, HQBatchAdmin)


class BillingLineItemInline(admin.TabularInline):
    """Inline for adding batch line items to HQ billing"""
    model = BillingLineItem
    extra = 0
    min_num = 0
    autocomplete_fields = ['batch']
    fields = ['site', 'batch', 'get_product', 'get_size', 'qty_for_invoice', 'selling_price']
    readonly_fields = ['get_product', 'get_size']
    
    class Media:
        js = ('js/billing_line_item_filter.js',)
    
    def get_queryset(self, request):
        """Optimize queryset with select_related for batch and product"""
        return super().get_queryset(request).select_related('batch', 'batch__product', 'site')
    
    def get_product(self, obj):
        """Get product name from batch"""
        if obj and obj.batch_id:
            from manufacturing.models import Batch
            try:
                batch = Batch.objects.select_related('product').get(pk=obj.batch_id)
                if batch.product:
                    return batch.product.product_name
            except Exception:
                pass
        return '-'
    get_product.short_description = 'Product'
    
    def get_size(self, obj):
        """Get size from batch"""
        if obj and obj.batch_id:
            from manufacturing.models import Batch
            try:
                batch = Batch.objects.get(pk=obj.batch_id)
                return batch.size or '-'
            except Exception:
                pass
        return '-'
    get_size.short_description = 'Size'
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'site':
            from tenants.models import Site
            kwargs['queryset'] = Site.objects.filter(is_active=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class HQBillingDocumentHeaderAdmin(BillingDocumentHeaderAdmin):
    change_list_template = 'hq_admin/billingdocumentheader_change_list.html'
    change_form_template = None  # Will be set dynamically in change_view and import_add_view
    
    # Add the line items inline (only shown for direct HQ billing, not imports)
    inlines = [BillingLineItemInline]
    
    def get_inlines(self, request, obj):
        """Only show inline for HQ direct billing, not for imports"""
        # Don't show inline for import view
        if getattr(self, '_is_import_view', False):
            return []
        # Don't show inline for imported records (editing)
        if obj and obj.pk and obj.import_source_site:
            return []
        # Show inline for HQ direct billing (add and edit)
        return [BillingLineItemInline]
    
    # Override list_display to remove production dates and add import source site
    list_display = [
        'base_number',
        'import_source_site_display',
        'client',
        'create_quote',
        'view_quote',
        'create_proforma',
        'view_proforma',
        'create_invoice',
        'view_invoice',
        'create_picking_slip',
        'view_picking_slip',
        'create_delivery_note',
        'view_delivery_note',
        'date_created',
    ]
    
    # Explicitly define Media to ensure billing_header.js loads (handles billing method radio button behavior)
    class Media:
        css = {
            'all': ('css/custom_admin.css',)
        }
        js = ('js/billing_header.js',)
    
    # Only client uses autocomplete (transporters uses form queryset filter)
    autocomplete_fields = ('client',)
    
    def import_source_site_display(self, obj):
        """Display which site this import came from"""
        if obj.import_source_site:
            return f"📍 {obj.import_source_site.name}"
        return "-"
    import_source_site_display.short_description = "Imported From Site"
    
    def get_list_display(self, request):
        """Override to ensure only HQ-specific columns are shown, no site field"""
        return self.list_display
    
    # Readonly fields for import view (view and email buttons)
    import_readonly_fields = [
        'view_quote', 'email_quote',
        'view_proforma', 'email_proforma',
        'view_invoice', 'email_invoice',
        'view_picking_slip', 'email_picking_slip',
        'view_delivery_note', 'email_delivery_note',
    ]
    
    def get_import_source_display(self, obj):
        """Display import source site"""
        if obj.import_source_site:
            return f"{obj.import_source_site.name}"
        return "-"
    get_import_source_display.short_description = "Imported From"
    
    
    # Fieldsets for HQ direct billing ADD (new records - simple without readonly methods)
    hq_direct_add_fieldsets = (
        (None, {
            'fields': (('client', 'delivery_institution', 'base_number'),),
        }),
        ("Dates", {
            'fields': (('billing_date', 'due_date'),),
        }),
        ("Financials", {
            'fields': (('from_currency', 'to_currency', 'exchange_rate', 'vat_percentage'),),
        }),
        ("Billing Method", {
            'classes': ('billing-method',),   
            'fields': (('bill_per_primary', 'bill_per_secondary', 'bill_per_pallet'),),
        }),
        ("Transport", {
            'classes': ('wide',),
            'fields': (('transporters', 'transport_cost'), 'dispatched'),
        }),
        ("Documents", {
            'fields': (
                ('create_quote', 'view_quote', 'email_quote'),
                ('create_proforma', 'view_proforma', 'email_proforma'),
                ('create_invoice', 'view_invoice', 'email_invoice'),
                ('create_picking_slip', 'view_picking_slip', 'email_picking_slip'),
                ('create_delivery_note', 'view_delivery_note', 'email_delivery_note'),
                'qty_for_invoice_data',
            ),
        }),
    )
    
    # Fieldsets for HQ direct billing EDIT (existing records - includes view/email fields)
    hq_direct_edit_fieldsets = (
        (None, {
            'fields': (('client', 'delivery_institution', 'base_number'),),
        }),
        ("Dates", {
            'fields': (('billing_date', 'due_date'),),
        }),
        ("Financials", {
            'fields': (('from_currency', 'to_currency', 'exchange_rate', 'vat_percentage'),),
        }),
        ("Billing Method", {
            'classes': ('billing-method',),   
            'fields': (('bill_per_primary', 'bill_per_secondary', 'bill_per_pallet'),),
        }),
        ("Transport", {
            'classes': ('wide',),
            'fields': (('transporters', 'transport_cost'), 'dispatched'),
        }),
        ("Documents", {
            'fields': (
                ('create_quote', 'view_quote', 'email_quote'),
                ('create_proforma', 'view_proforma', 'email_proforma'),
                ('create_invoice', 'view_invoice', 'email_invoice'),
                ('create_picking_slip', 'view_picking_slip', 'email_picking_slip'),
                ('create_delivery_note', 'view_delivery_note', 'email_delivery_note'),
                'qty_for_invoice_data',
            ),
        }),
    )
    
    # Fieldsets for import view (matching site billing layout with Documents in rows)
    import_fieldsets = (
        (None, {
            'fields': (('site', 'invoice_number'), ('client', 'delivery_institution', 'base_number')),
        }),
        ("Dates", {
            'fields': (('billing_date', 'due_date'),),
        }),
        ("Financials", {
            'fields': (('from_currency', 'to_currency', 'exchange_rate', 'vat_percentage'),),
        }),
        ("Billing Method", {
            'classes': ('billing-method',),   
            'fields': (('bill_per_primary', 'bill_per_secondary', 'bill_per_pallet'),),
        }),
        ("Transport", {
            'classes': ('wide',),
            'fields': (('transporters', 'transport_cost'), 'dispatched'),
        }),
        ("Documents", {
            'fields': (
                ('create_quote', 'view_quote', 'email_quote'),
                ('create_proforma', 'view_proforma', 'email_proforma'),
                ('create_invoice', 'view_invoice', 'email_invoice'),
                ('create_picking_slip', 'view_picking_slip', 'email_picking_slip'),
                ('create_delivery_note', 'view_delivery_note', 'email_delivery_note'),
                'qty_for_invoice_data',
            ),
        }),
    )
    
    # Fieldsets for viewing/editing imported records (read-only import source)
    import_view_fieldsets = (
        (None, {
            'fields': (('get_import_source_display', 'import_source_invoice_number'), ('client', 'delivery_institution', 'base_number')),
        }),
        ("Dates", {
            'fields': (('billing_date', 'due_date'),),
        }),
        ("Financials", {
            'fields': (('from_currency', 'to_currency', 'exchange_rate', 'vat_percentage'),),
        }),
        ("Billing Method", {
            'classes': ('billing-method',),   
            'fields': (('bill_per_primary', 'bill_per_secondary', 'bill_per_pallet'),),
        }),
        ("Transport", {
            'classes': ('wide',),
            'fields': (('transporters', 'transport_cost'), 'dispatched'),
        }),
        ("Documents", {
            'fields': (
                ('create_quote', 'view_quote', 'email_quote'),
                ('create_proforma', 'view_proforma', 'email_proforma'),
                ('create_invoice', 'view_invoice', 'email_invoice'),
                ('create_picking_slip', 'view_picking_slip', 'email_picking_slip'),
                ('create_delivery_note', 'view_delivery_note', 'email_delivery_note'),
                'qty_for_invoice_data',
            ),
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).filter(site__isnull=True)
    
    def get_urls(self):
        """Add custom import URL"""
        urls = super().get_urls()
        custom_urls = [
            path('import/add/', self.admin_site.admin_view(self.import_add_view), name='billingdocumentheader_import_add'),
        ]
        return custom_urls + urls
    
    def get_form(self, request, obj=None, **kwargs):
        """Override to ensure readonly fields are available before form validation"""
        # Get readonly fields early so they're available during fieldsets validation
        # This must be done before calling super().get_form()
        if 'fields' not in kwargs:
            # Pre-populate readonly list for validation
            if getattr(self, '_is_import_view', False) or getattr(self, '_is_hq_direct_add', False) or (obj and obj.pk):
                # Temporarily set readonly_fields for the form creation
                if not hasattr(self, '_original_readonly_fields'):
                    self._original_readonly_fields = None
                kwargs['readonly_fields'] = self.get_readonly_fields(request, obj)
        
        return super().get_form(request, obj, **kwargs)
    
    def import_add_view(self, request, form_url='', extra_context=None):
        """Custom add view for import billing using ImportBillingForm"""
        # Temporarily store the import flag
        self._is_import_view = True
        # Use the original import template (no inline)
        self.change_form_template = 'admin/costing/billingdocumentheader/import_change_form.html'
        try:
            return self.add_view(request, form_url, extra_context)
        finally:
            self._is_import_view = False
            self.change_form_template = None
    
    def add_view(self, request, form_url='', extra_context=None):
        """Override add_view to handle HQ direct billing (not imports)"""
        # If this is NOT an import view, it's HQ direct billing
        # Set flag to ensure get_readonly_fields includes view/email methods
        if not getattr(self, '_is_import_view', False):
            self._is_hq_direct_add = True
            self.change_form_template = 'hq_admin/hq_billing_change_form.html'
        try:
            return super().add_view(request, form_url, extra_context)
        finally:
            if hasattr(self, '_is_hq_direct_add'):
                del self._is_hq_direct_add
            self.change_form_template = None
    
    def change_view(self, request, object_id, form_url='', extra_context=None):
        """Override change view to use appropriate template"""
        try:
            obj = self.get_object(request, object_id)
            if obj and obj.site is None:
                # Check if this is an imported record
                if obj.import_source_site:
                    # Imported record - use import template (no inline)
                    self.change_form_template = 'admin/costing/billingdocumentheader/import_change_form.html'
                else:
                    # HQ direct billing - use template with inline
                    self.change_form_template = 'hq_admin/hq_billing_change_form.html'
            else:
                self.change_form_template = None
        except:
            pass
        
        try:
            return super().change_view(request, object_id, form_url, extra_context)
        finally:
            self.change_form_template = None
    
    def get_form(self, request, obj=None, **kwargs):
        """Use appropriate form based on context"""
        # Import view uses ImportBillingForm (with site/invoice_number)
        if getattr(self, '_is_import_view', False):
            return ImportBillingForm
        
        # Editing imported records uses ImportBillingForm
        if obj and obj.pk and obj.import_source_site:
            return ImportBillingForm
        
        # HQ direct add/edit uses HQDirectBillingForm (without import fields)
        return HQDirectBillingForm
    
    def get_fieldsets(self, request, obj=None):
        """Use appropriate fieldsets based on record type"""
        # For creating a new import, use standard import_fieldsets (with site selector)
        if getattr(self, '_is_import_view', False):
            return self.import_fieldsets
        
        # If editing an imported HQ billing record (import_source_site is set), use import_view_fieldsets (readonly source)
        if obj and obj.pk and obj.import_source_site:
            return self.import_view_fieldsets
        
        # For direct HQ billing (not imports)
        # Use different fieldsets for add vs edit (view/email fields only available after save)
        if obj and obj.pk:
            return self.hq_direct_edit_fieldsets
        else:
            return self.hq_direct_add_fieldsets
    
    def get_readonly_fields(self, request, obj=None):
        """Include view/email fields in readonly for import view and regular edit"""
        base_readonly = list(super().get_readonly_fields(request, obj))
        
        # For import view, add view/email methods as readonly fields
        if getattr(self, '_is_import_view', False):
            base_readonly.extend(self.import_readonly_fields)
            return base_readonly
        
        # For HQ direct ADD - add view/email methods as readonly fields
        if getattr(self, '_is_hq_direct_add', False):
            base_readonly.extend(self.import_readonly_fields)
            return base_readonly
        
        # For imported records (editing HQ records with import_source_site set)
        # Show the import source display method and make import_source_invoice_number readonly
        if obj and obj.pk and obj.import_source_site:
            base_readonly.extend(['get_import_source_display', 'import_source_invoice_number'])
            # Also add view/email methods for imported records
            if hasattr(self, 'import_readonly_fields'):
                base_readonly.extend(self.import_readonly_fields)
            return base_readonly
        
        # For HQ direct billing EDIT - add view/email fields
        if obj and obj.pk:
            # Add view/email fields
            if hasattr(self, 'import_readonly_fields'):
                for field in self.import_readonly_fields:
                    if field not in base_readonly:
                        base_readonly.append(field)
        
        return base_readonly
    
    def save_model(self, request, obj, form, change):
        """Force site=NULL for NEW HQ billing records, but preserve for edits to imported records"""
        # Only force site=NULL for new records, not when editing imported records
        if not change:  # change=False means it's a new record
            obj.site = None
        
        # ALWAYS set the correct company for PDF/document generation based on site
        from commercial.models import CompanyDetails
        if obj.site:
            # For site records, use site's company
            obj.company = CompanyDetails.objects.filter(site=obj.site, is_active=True).first()
        else:
            # For HQ records (site=NULL), ALWAYS use HQ company (site__isnull=True)
            obj.company = CompanyDetails.objects.filter(site__isnull=True, is_active=True).first()
        
        super().save_model(request, obj, form, change)


# Incident Management Models - HQ data only (site=NULL)
from incident_management.models import Incident
from incident_management.admin import IncidentAdmin

class HQIncidentDirectForm(forms.ModelForm):
    """
    Form for creating HQ incidents directly (not imported).
    Includes 'site' field for batch filtering only (not saved).
    """
    site = forms.ModelChoiceField(
        queryset=None,
        required=False,
        help_text="Used for batch filtering only (not saved). Select a site to filter batches."
    )
    
    class Meta:
        model = Incident
        fields = [
            'site',  # For batch filtering only, not saved
            'production_date',
            'batch',
            'incident_date',
            'location',
            'investigation_start',
            'investigation_end',
            'report_date',
            'responsible_person',
            'management_person',
            'description',
            'incident_report',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from tenants.models import Site
        from manufacturing.models import Batch
        
        # Set up site field (for filtering batches only)
        if 'site' in self.fields:
            self.fields['site'].queryset = Site.objects.all()
            self.fields['site'].required = False
        
        # Initialize batch queryset
        if self.instance and self.instance.pk:
            # Editing existing incident - filter batches by the batch's site
            if hasattr(self.instance, 'batch') and self.instance.batch and self.instance.batch.site:
                batch_site = self.instance.batch.site
                self.initial['site'] = batch_site
                if 'site' in self.fields:
                    self.fields['site'].initial = batch_site
                
                # CRITICAL: Filter batch queryset to only show batches from this site and production date
                if 'batch' in self.fields and self.instance.production_date:
                    self.fields['batch'].queryset = Batch.objects.filter(
                        site=batch_site,
                        production_date=self.instance.production_date
                    ).order_by('batch_number')
                elif 'batch' in self.fields:
                    # If no production date, show batches from the site only
                    self.fields['batch'].queryset = Batch.objects.filter(
                        site=batch_site
                    ).order_by('batch_number')
        elif not self.data:
            # New incident form (GET request): Start with empty batch queryset
            if 'batch' in self.fields:
                self.fields['batch'].queryset = Batch.objects.none()
        else:
            # Form submitted (POST) - filter batches if site is selected
            site_id = self.data.get('site')
            production_date = self.data.get('production_date')
            
            if site_id and 'batch' in self.fields:
                queryset = Batch.objects.filter(site_id=site_id)
                if production_date:
                    # Try to parse the date and filter
                    try:
                        from django.utils.dateparse import parse_date
                        parsed_date = parse_date(production_date)
                        if parsed_date:
                            queryset = queryset.filter(production_date=parsed_date)
                    except:
                        pass
                self.fields['batch'].queryset = queryset.order_by('batch_number')

    def save(self, commit=True):
        instance = super().save(commit=False)
        # CRITICAL: Ensure HQ incidents always have site=NULL
        instance.site = None
        if commit:
            instance.save()
        return instance


class HQIncidentImportForm(forms.ModelForm):
    """
    Form for importing incidents from site to HQ.
    Shows site selector → incident selector, then auto-fills all data.
    """
    # Add date fields with proper widgets
    investigation_start = forms.DateField(
        required=True,
        input_formats=["%d-%m-%Y", "%Y-%m-%d"],
        widget=forms.DateInput(
            format="%d-%m-%Y",
            attrs={"class": "vDateField"},
        ),
    )
    investigation_end = forms.DateField(
        required=True,
        input_formats=["%d-%m-%Y", "%Y-%m-%d"],
        widget=forms.DateInput(
            format="%d-%m-%Y",
            attrs={"class": "vDateField"},
        ),
    )
    report_date = forms.DateField(
        required=True,
        input_formats=["%d-%m-%Y", "%Y-%m-%d"],
        widget=forms.DateInput(
            format="%d-%m-%Y",
            attrs={"class": "vDateField"},
        ),
    )
    
    class Meta:
        model = Incident
        fields = [
            'import_source_site',
            'import_source_incident',
            'investigation_start',
            'investigation_end',
            'report_date',
            'responsible_person',
            'management_person',
            'incident_report',
        ]
        widgets = {
            'import_source_site': forms.Select(attrs={'id': 'id_import_source_site'}),
            'import_source_incident': forms.Select(attrs={'id': 'id_import_source_incident'}),
        }

    class Media:
        js = ('admin/js/vendor/jquery/jquery.js',)
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from tenants.models import Site
        
        # Set up import source fields
        if 'import_source_site' in self.fields:
            self.fields['import_source_site'].queryset = Site.objects.all()
            self.fields['import_source_site'].required = True
            self.fields['import_source_site'].label = "Select Site"
            self.fields['import_source_site'].help_text = "Choose the site from which to import an incident"
        
        if 'import_source_incident' in self.fields:
            # Check if we're editing an existing imported incident
            if self.instance and self.instance.pk and hasattr(self.instance, 'import_source_site') and self.instance.import_source_site:
                # Editing existing - populate incidents from the saved source site
                self.fields['import_source_incident'].queryset = Incident.objects.filter(
                    site=self.instance.import_source_site,
                    is_archived=False
                ).order_by('-incident_date')
            # Or if there's an import source site in POST data, populate incident options
            elif self.data.get('import_source_site'):
                try:
                    site_id = int(self.data.get('import_source_site'))
                    self.fields['import_source_incident'].queryset = Incident.objects.filter(
                        site_id=site_id,
                        is_archived=False
                    ).order_by('-incident_date')
                    
                    # If incident is selected, pre-populate form fields with incident data
                    if self.data.get('import_source_incident'):
                        try:
                            incident_id = int(self.data.get('import_source_incident'))
                            source_incident = Incident.objects.get(pk=incident_id)
                            
                            # Pre-populate the form fields with source incident data
                            if 'investigation_start' in self.fields and not self.initial.get('investigation_start'):
                                self.initial['investigation_start'] = source_incident.investigation_start
                            if 'investigation_end' in self.fields and not self.initial.get('investigation_end'):
                                self.initial['investigation_end'] = source_incident.investigation_end
                            if 'report_date' in self.fields and not self.initial.get('report_date'):
                                self.initial['report_date'] = source_incident.report_date
                            if 'responsible_person' in self.fields and not self.initial.get('responsible_person'):
                                self.initial['responsible_person'] = source_incident.responsible_person
                            if 'management_person' in self.fields and not self.initial.get('management_person'):
                                self.initial['management_person'] = source_incident.management_person
                        except (ValueError, TypeError, Incident.DoesNotExist):
                            pass
                except (ValueError, TypeError):
                    self.fields['import_source_incident'].queryset = Incident.objects.none()
            else:
                self.fields['import_source_incident'].queryset = Incident.objects.none()
            
            self.fields['import_source_incident'].required = True
            self.fields['import_source_incident'].label = "Select Incident to Import"
            self.fields['import_source_incident'].help_text = "Choose the incident to import (select site first)"

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Copy all data from source incident (if selected)
        if hasattr(instance, 'import_source_incident') and instance.import_source_incident:
            source = instance.import_source_incident
            instance.incident_date = source.incident_date
            instance.production_date = source.production_date
            instance.batch = source.batch
            instance.location = source.location
            instance.description = source.description
            # Keep the user-entered investigation dates, responsible parties, and report file
            # (these are in the form and can be modified)
        
        # CRITICAL: Ensure HQ incidents always have site=NULL
        instance.site = None
        
        if commit:
            instance.save()
        return instance




class HQIncidentAdmin(IncidentAdmin):
    change_list_template = 'hq_admin/incident_changelist.html'
    change_form_template = 'hq_admin/incident_change_form.html'
    
    def change_view(self, request, object_id, form_url='', extra_context=None):
        """Override to add mode=import for imported incidents"""
        # If no mode parameter is present, check if this is an imported incident
        if not request.GET.get('mode') and not request.POST.get('_mode'):
            try:
                obj = self.get_object(request, object_id)
                if obj and hasattr(obj, 'import_source_incident') and obj.import_source_incident:
                    # This is an imported incident - redirect with mode=import
                    from django.http import HttpResponseRedirect
                    # Get current URL path and add mode=import parameter
                    current_path = request.path
                    return HttpResponseRedirect(f'{current_path}?mode=import')
            except:
                pass
        
        return super().change_view(request, object_id, form_url, extra_context)
    
    # Remove inlines for import mode (no attachments in import form)
    def get_inline_instances(self, request, obj=None):
        """Remove attachments inline when importing"""
        # Check GET parameter first, then POST parameter (_mode hidden field)
        mode = request.GET.get('mode') or request.POST.get('_mode')
        if mode == 'import':
            # Import mode - no attachments (even after save)
            return []
        return super().get_inline_instances(request, obj)
    
    def get_queryset(self, request):
        return super().get_queryset(request).filter(site__isnull=True)
    
    def get_form(self, request, obj=None, **kwargs):
        """
        Return different form based on mode:
        - ?mode=import → HQIncidentImportForm (site + incident selector)
        - Default → HQIncidentDirectForm (direct creation)
        """
        # Check GET parameter first, then POST parameter (_mode hidden field)
        mode = request.GET.get('mode') or request.POST.get('_mode')
        
        if mode == 'import':
            # Import mode - show site and incident selector (even after save)
            kwargs['form'] = HQIncidentImportForm
        else:
            # Direct mode (default) - show direct creation fields
            kwargs['form'] = HQIncidentDirectForm
        
        return super().get_form(request, obj, **kwargs)
    
    def get_urls(self):
        """Add custom URL for AJAX incident loading"""
        urls = super().get_urls()
        custom_urls = [
            path('site-incidents/', self.site_incidents_json, name='incident_site_incidents'),
        ]
        return custom_urls + urls
    
    def site_incidents_json(self, request):
        """Return incidents for a selected site as JSON"""
        from django.http import JsonResponse
        
        site_id = request.GET.get('site_id')
        if not site_id:
            return JsonResponse([], safe=False)
        
        try:
            incidents = Incident.objects.filter(
                site_id=int(site_id),
                is_archived=False
            ).order_by('-incident_date')
            
            data = [
                {
                    'id': inc.pk,
                    'display': f'Incident {inc.pk} ({inc.incident_date}) - {inc.location}'
                }
                for inc in incidents
            ]
            
            return JsonResponse(data, safe=False)
        except (ValueError, TypeError):
            return JsonResponse([], safe=False)
    
    def import_source_incident_link(self, obj):
        """Display hyperlink to source incident (site admin)"""
        if obj and hasattr(obj, 'import_source_incident') and obj.import_source_incident and hasattr(obj, 'import_source_site') and obj.import_source_site:
            site = obj.import_source_site
            incident = obj.import_source_incident
            url = f'/hq/{site.slug}/admin/incident_management/incident/{incident.pk}/change/'
            # Format date as DD-MM-YYYY
            date_str = incident.incident_date.strftime('%d-%m-%Y') if incident.incident_date else 'N/A'
            return format_html(
                '<a href="{}">Incident {} - {}</a>',
                url,
                incident.pk,
                date_str
            )
        return '-'
    import_source_incident_link.short_description = 'Source Incident'
    
    def import_source_site_display(self, obj):
        """Display source site as plain text (no hyperlink)"""
        if obj and hasattr(obj, 'import_source_site') and obj.import_source_site:
            return obj.import_source_site.name
        return '-'
    import_source_site_display.short_description = 'Source Site'
    
    def get_readonly_fields(self, request, obj=None):
        """Make certain fields readonly when importing"""
        readonly = list(super().get_readonly_fields(request, obj))
        
        # Check if we're in import mode
        mode = request.GET.get('mode') or request.POST.get('_mode')
        
        if mode == 'import' and obj:
            # In import mode after save - make source fields readonly, keep rest editable
            readonly.append('import_source_site_display')
            readonly.append('import_source_incident_link')
            # Don't add investigation dates, responsible parties, or report file - keep them editable
        elif obj and hasattr(obj, 'import_source_incident') and obj.import_source_incident:
            # Imported incident viewed WITHOUT mode=import - make everything readonly
            readonly.append('import_source_incident_link')
            readonly.extend([
                'incident_date', 'production_date', 'batch', 'location',
                'investigation_start', 'investigation_end', 'report_date',
                'responsible_person', 'management_person', 'description'
            ])
        
        return readonly
    
    def get_fieldsets(self, request, obj=None):
        """
        Return different fieldsets based on mode and whether editing imported incident.
        - ?mode=import → Show import fields only (site + incident selector)
        - Default (direct) → Show direct creation fields
        - Editing imported (without mode=import) → Show imported data with tracking section
        """
        # Check GET parameter first, then POST parameter (_mode hidden field)
        mode = request.GET.get('mode') or request.POST.get('_mode')
        
        # If mode=import is explicitly set, always show import form (even after save)
        if mode == 'import':
            # After save, show readonly text for site and link for incident
            site_field = 'import_source_site_display' if obj else 'import_source_site'
            incident_field = 'import_source_incident_link' if obj else 'import_source_incident'
            
            return (
                ("Import Incident from Site", {
                    'fields': (
                        site_field,
                        incident_field,
                    ),
                    'description': 'Select a site and then choose an incident to import. All incident data will be copied automatically.'
                }),
                ("Investigation Timeline", {
                    'fields': (
                        ('investigation_start', 'investigation_end', 'report_date'),
                    )
                }),
                ("Responsible Parties", {
                    'fields': (
                        ('responsible_person', 'management_person'),
                    )
                }),
                ("Upload Main Report File", {
                    'fields': ('incident_report',)
                }),
            )
        
        # Check if this is an imported incident (editing existing WITHOUT mode=import)
        is_imported = obj and hasattr(obj, 'import_source_incident') and obj.import_source_incident
        
        if is_imported:
            # Editing an imported incident - show all data with import tracking
            return (
                ("Incident Information", {
                    'fields': (
                        ('incident_date', 'location'),
                        ('production_date', 'batch'),
                        'description',
                    )
                }),
                ("Import Tracking", {
                    'fields': (
                        ('import_source_site_display', 'import_source_incident_link'),
                    ),
                    'classes': ('collapse',),
                }),
                ("Investigation Timeline", {
                    'fields': (
                        ('investigation_start', 'investigation_end', 'report_date'),
                    )
                }),
                ("Responsible Parties", {
                    'fields': (
                        ('responsible_person', 'management_person'),
                    )
                }),
                ("Upload Main Report File", {
                    'fields': ('incident_report',)
                }),
                ("System Info", {
                    'fields': ('created',),
                    'classes': ('collapse',),
                })
            )
        else:
            # Direct mode - creating or editing direct incident
            fieldsets = [
                ("Incident Information", {
                    'fields': (
                        'site',  # For batch filtering only
                        ('incident_date', 'production_date', 'batch'),
                        'location',
                        'description'
                    ),
                    'description': 'Site field is used only for filtering batches and will not be saved.'
                }),
                ("Investigation Timeline", {
                    'fields': (
                        ('investigation_start', 'investigation_end', 'report_date'),
                    )
                }),
                ("Responsible Parties", {
                    'fields': (
                        ('responsible_person', 'management_person'),
                    )
                }),
                ("Upload Main Report File", {
                    'fields': ('incident_report',)
                }),
            ]
            
            # Add System Info only when editing
            if obj is not None:
                fieldsets.append(
                    ("System Info", {
                        'fields': ('created',),
                        'classes': ('collapse',),
                    })
                )
            
            return tuple(fieldsets)
    
    def response_add(self, request, obj, post_url_continue=None):
        """Preserve mode parameter in redirect URL after add"""
        from django.http import HttpResponseRedirect
        response = super().response_add(request, obj, post_url_continue)
        
        # If mode=import was in the request, preserve it in redirect
        mode = request.GET.get('mode') or request.POST.get('_mode')
        if mode == 'import' and isinstance(response, HttpResponseRedirect):
            url = response['Location']
            if '?' in url:
                response['Location'] = url + '&mode=import'
            else:
                response['Location'] = url + '?mode=import'
        
        return response
    
    def response_change(self, request, obj):
        """Preserve mode parameter in redirect URL after change"""
        from django.http import HttpResponseRedirect
        response = super().response_change(request, obj)
        
        # If this is an imported incident, preserve mode=import
        mode = request.GET.get('mode') or request.POST.get('_mode')
        if mode == 'import' and isinstance(response, HttpResponseRedirect):
            url = response['Location']
            if '?' in url:
                response['Location'] = url + '&mode=import'
            else:
                response['Location'] = url + '?mode=import'
        
        return response



# Inventory Models - HQ data only (site=NULL)
from inventory.models import PurchaseOrder, HQPOLineItem
from inventory.admin import PurchaseOrderAdmin
from product_details.models import ProductCategory, Product


class HQPOLineItemForm(forms.ModelForm):
    """
    Custom form for HQ PO line items.
    Flow: Category → Product Name → SKU → Size (readonly)
    The 'product' FK is hidden and set via JS from the SKU selection.
    """
    product_name_select = forms.CharField(
        required=False,
        label="Product",
        widget=forms.Select(choices=[('', '---------')]),
    )
    sku_select = forms.CharField(
        required=False,
        label="SKU",
        widget=forms.Select(choices=[('', '---------')]),
    )
    size_display = forms.CharField(
        required=False,
        label="Size",
        widget=forms.TextInput(attrs={'readonly': 'readonly', 'style': 'background:#f0f0f0; border:1px solid #ccc;'}),
    )

    class Meta:
        model = HQPOLineItem
        fields = ['category', 'product', 'quantity', 'unit_price']
        widgets = {
            'product': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].required = False
        # Pre-populate for existing records
        if self.instance and self.instance.pk and self.instance.product:
            prod = self.instance.product
            cat = self.instance.category
            # Product name choices
            names = list(
                Product.objects.filter(category=cat, is_archived=False)
                .values_list('product_name', flat=True)
                .distinct().order_by('product_name')
            )
            self.fields['product_name_select'].widget = forms.Select(
                choices=[('', '---------')] + [(n, n) for n in names]
            )
            self.initial['product_name_select'] = prod.product_name
            # SKU choices (value = product PK, label = SKU or product name)
            variants = Product.objects.filter(
                product_name=prod.product_name, category=cat, is_archived=False
            )
            sku_choices = [('', '---------')]
            for v in variants:
                label = v.sku if v.sku else f'{v.product_name} ({v.size or "no size"})'
                sku_choices.append((str(v.pk), label))
            self.fields['sku_select'].widget = forms.Select(choices=sku_choices)
            self.initial['sku_select'] = str(prod.pk)
            # Size
            self.initial['size_display'] = prod.size or '-'

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Set product from sku_select (which holds product PK)
        sku_val = self.cleaned_data.get('sku_select')
        if sku_val:
            try:
                instance.product = Product.objects.get(pk=int(sku_val), is_archived=False)
            except (Product.DoesNotExist, ValueError, TypeError):
                pass
        if commit:
            instance.save()
        return instance


class HQPOLineItemInline(admin.TabularInline):
    """Inline: Category → Product Name → SKU → Size (readonly) + Qty + Price + Line Total"""
    model = HQPOLineItem
    form = HQPOLineItemForm
    extra = 0
    min_num = 0
    fields = (
        'category', 'product_name_select', 'sku_select', 'size_display',
        'product',  # hidden FK
        'quantity', 'unit_price', 'line_total_display',
    )
    readonly_fields = ('line_total_display',)

    class Media:
        js = ('js/hq_po_line_item.js',)

    def line_total_display(self, obj):
        if obj and obj.pk:
            return f"R {obj.line_total:,.2f}"
        return 'R 0.00'
    line_total_display.short_description = 'Line Total'

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'category':
            kwargs['queryset'] = ProductCategory.objects.all().order_by('name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class HQPurchaseOrderAdminForm(forms.ModelForm):
    order_date = forms.DateField(
        widget=forms.DateInput(format='%d-%m-%Y', attrs={'class': 'vDateField', 'size': '10'}),
        input_formats=['%d-%m-%Y', '%d/%m/%Y', '%Y-%m-%d'],
    )
    due_date = forms.DateField(
        required=False,
        widget=forms.DateInput(format='%d-%m-%Y', attrs={'class': 'vDateField', 'size': '10'}),
        input_formats=['%d-%m-%Y', '%d/%m/%Y', '%Y-%m-%d'],
    )

    class Meta:
        model = PurchaseOrder
        fields = ['site', 'po_number', 'status', 'order_date', 'due_date',
                  'currency', 'vat_percentage', 'notes']

    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)  # Pop request from kwargs (passed by parent's get_form)
        super().__init__(*args, **kwargs)
        # Only show active sites
        self.fields['site'].queryset = Site.objects.filter(is_active=True, is_archived=False)
        self.fields['site'].label = "Site"
        self.fields['site'].required = True


class HQPurchaseOrderAdmin(PurchaseOrderAdmin):
    form = HQPurchaseOrderAdminForm
    inlines = [HQPOLineItemInline]
    change_form_template = None  # Use default admin template

    @property
    def media(self):
        """Override to exclude parent's site-PO JS files (po_inline_move.js, po_currency_switch.js)."""
        extra = '' if self.actions is not None and bool(self.actions) else ''
        base_media = super(PurchaseOrderAdmin, self).media  # Skip parent's Media class
        # Add only our JS
        return base_media + forms.Media(
            js=('js/hq_po_line_item.js',),
            css={'all': ('css/po_admin.css',)},
        )

    list_display = (
        'po_number', 'order_date_display', 'due_date_display',
        'site', 'currency', 'hq_total_display', 'status',
        'view_po', 'email_po',
    )
    list_filter = ('status', 'currency', 'order_date', 'site')
    search_fields = ('po_number', 'site__name')

    fieldsets = (
        ('Order Information', {
            'fields': (
                ('po_number', 'status'),
                ('order_date', 'due_date'),
            ),
        }),
        ('Site', {
            'fields': ('site',),
        }),
        ('Totals', {
            'fields': (('currency', 'vat_percentage', 'hq_total_amount_display'),),
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',),
        }),
    )

    readonly_fields = ('hq_total_amount_display',)
    exclude = ('order_type', 'supplier', 'category', 'sub_category', 'create_po')

    def get_queryset(self, request):
        return super(PurchaseOrderAdmin, self).get_queryset(request).filter(is_hq_order=True)

    def save_model(self, request, obj, form, change):
        """Mark as HQ order on save."""
        obj.is_hq_order = True
        if not obj.order_type:
            obj.order_type = 'Local'
        super().save_model(request, obj, form, change)

    def hq_total_display(self, obj):
        """List display total"""
        if obj and obj.pk:
            currency_symbols = {'R': 'R', 'NAD': 'N$', 'USD': '$', 'EUR': '€'}
            symbol = currency_symbols.get(obj.currency, obj.currency)
            total = sum(item.line_total for item in obj.hq_line_items.all())
            vat_amount = total * (obj.vat_percentage / 100)
            grand_total = total + vat_amount
            return f"{symbol} {grand_total:,.2f}"
        return "R 0.00"
    hq_total_display.short_description = "Total"

    def hq_total_amount_display(self, obj):
        """Form display total"""
        if obj and obj.pk:
            currency_symbols = {'R': 'R', 'NAD': 'N$', 'USD': '$', 'EUR': '€'}
            symbol = currency_symbols.get(obj.currency, obj.currency)
            total = sum(item.line_total for item in obj.hq_line_items.all())
            vat_amount = total * (obj.vat_percentage / 100)
            grand_total = total + vat_amount
            formatted = f"{symbol} {grand_total:,.2f}"
        else:
            formatted = "R 0.00"
        from django.utils.html import format_html
        return format_html('<span id="po-grand-total-display">{}</span>', formatted)
    hq_total_amount_display.short_description = "Total Amount (Incl VAT)"

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('get-categories-by-site/',
                 self.admin_site.admin_view(self.get_categories_by_site_view),
                 name='hq_po_get_categories_by_site'),
            path('get-product-names/',
                 self.admin_site.admin_view(self.get_product_names_view),
                 name='hq_po_get_product_names'),
            path('get-skus/',
                 self.admin_site.admin_view(self.get_skus_view),
                 name='hq_po_get_skus'),
        ]
        return custom_urls + urls

    def get_categories_by_site_view(self, request):
        """Return ProductCategories for the selected site."""
        from django.http import JsonResponse
        from django.db.models import Q
        site_id = request.GET.get('site_id')
        if not site_id:
            return JsonResponse({'categories': []})
        categories = ProductCategory.objects.filter(
            Q(site_id=site_id) | Q(site__isnull=True)
        ).values('id', 'name').order_by('name')
        return JsonResponse({'categories': list(categories)})

    def get_product_names_view(self, request):
        """Return unique product names for a category+site."""
        from django.http import JsonResponse
        from django.db.models import Q
        category_id = request.GET.get('category_id')
        site_id = request.GET.get('site_id')
        if not category_id:
            return JsonResponse({'product_names': []})
        qs = Product.objects.filter(category_id=category_id, is_archived=False)
        if site_id:
            qs = qs.filter(Q(site_id=site_id) | Q(site__isnull=True))
        names = list(qs.values_list('product_name', flat=True).distinct().order_by('product_name'))
        return JsonResponse({'product_names': names})

    def get_skus_view(self, request):
        """Return product variants (id, sku, size) for a product name + category."""
        from django.http import JsonResponse
        product_name = request.GET.get('product_name')
        category_id = request.GET.get('category_id')
        if not product_name:
            return JsonResponse({'skus': []})
        qs = Product.objects.filter(product_name=product_name, is_archived=False)
        if category_id:
            qs = qs.filter(category_id=category_id)
        skus = []
        for p in qs.order_by('sku'):
            label = p.sku if p.sku else f'{p.product_name} ({p.size or "no size"})'
            skus.append({'id': p.id, 'label': label, 'size': p.size or '-'})
        return JsonResponse({'skus': skus})

    class Media:
        css = {'all': ('css/po_admin.css',)}
        # Intentionally empty js - see media property override above
        js = ()

# Manufacturing Models - HQ data only (site=NULL)
from manufacturing.models import ManufacturingReport
from manufacturing.admin import ManufacturingReportAdmin

class HQManufacturingReportAdmin(ManufacturingReportAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).filter(site__isnull=True)

# Transport Models - HQ data only (site=NULL)
from transport.models import TransportLoad, DeliverySite
from transport.admin import TransportLoadAdmin, DeliverySiteAdmin

class HQTransportLoadAdmin(TransportLoadAdmin):
    """
    HQ Transport Load Admin
    Transport loads are created automatically via signals when billing is marked as dispatched.
    Shows import tracking if billing was imported from a site.
    """
    # Remove import button from template since transport is auto-created
    change_list_template = None  # Use default admin template
    
    # Override list_display to show import source and billing link
    list_display = [
        'load_number',
        'import_source_display',
        'billing_document',
        'client',
        'delivery_institution',
        'billing_date',
        'released_date',
        'transporter',
    ]
    
    def import_source_display(self, obj):
        """Display which site this was imported from (if any)"""
        if obj.import_source_site and obj.import_source_load_number:
            return f"📍 {obj.import_source_site.name} (Load {obj.import_source_load_number})"
        return "-"
    import_source_display.short_description = "Import Source"
    
    # Fieldsets for viewing HQ transport
    fieldsets = (
        ("Information", {
            'fields': (
                ('load_number', 'billing_document'),
                ('client', 'delivery_institution'),
                ('billing_date', 'released_date', 'date_loaded'),
            ),
        }),
        ("Import Tracking", {
            'fields': (
                ('import_source_site', 'import_source_load_number_link', 'load_total_display'),
            ),
            'classes': ('collapse',),
        }),
        ("Transport", {
            'fields': (
                ('transporter', 'transport_cost'),
            ),
        }),
        ("Documents", {
            'fields': (
                'custom_documents_display',
            ),
        }),
    )
    
    def get_fieldsets(self, request, obj=None):
        """Conditionally include Import Tracking section only for imported billings"""
        fieldsets = super().get_fieldsets(request, obj)
        
        # If this is a Direct Billing (no import_source_site), remove Import Tracking section
        if obj and obj.billing_document and not obj.billing_document.import_source_site:
            # Remove Import Tracking section and move Load Total Qty to Information section
            fieldsets = (
                ("Information", {
                    'fields': (
                        ('load_number', 'billing_document'),
                        ('client', 'delivery_institution', 'load_total_display'),
                        ('billing_date', 'released_date', 'date_loaded'),
                    ),
                }),
                ("Transport", {
                    'fields': (
                        ('transporter', 'transport_cost'),
                    ),
                }),
                ("Documents", {
                    'fields': (
                        'custom_documents_display',
                    ),
                }),
            )
        
        return fieldsets
    
    def get_queryset(self, request):
        """Show only HQ transport loads (site=NULL)"""
        return super().get_queryset(request).filter(site__isnull=True)
    
    def get_readonly_fields(self, request, obj=None):
        """Set readonly fields - make load_number editable"""
        base_readonly = list(super().get_readonly_fields(request, obj))
        
        # Remove load_number from readonly so it can be edited
        if 'load_number' in base_readonly:
            base_readonly.remove('load_number')
        
        # Make only auto-populated fields readonly
        readonly_fields = [
            'billing_document', 'client', 'delivery_institution',
            'billing_date', 'released_date', 'date_loaded', 'transport_cost',
            'transporter', 'import_source_site', 'import_source_load_number_link',
            'custom_documents_display', 'load_total_display'
        ]
        
        for field in readonly_fields:
            if field not in base_readonly:
                base_readonly.append(field)
        
        return base_readonly
    
    def import_source_load_number_link(self, obj):
        """Create hyperlink to site load if import data exists"""
        if not obj.import_source_site or not obj.import_source_load_number:
            return "-"
        
        # Try to find the transport load in the site database
        from transport.models import TransportLoad
        try:
            site_load = TransportLoad.objects.filter(
                site=obj.import_source_site,
                load_number=obj.import_source_load_number
            ).first()
            
            if site_load:
                # Create link to site admin
                from django.urls import reverse
                url = reverse(
                    'admin:transport_transportload_change',
                    args=[site_load.pk],
                )
                # Update URL to site admin context
                url = f"/hq/{obj.import_source_site.slug}/admin/transport/transportload/{site_load.pk}/change/"
                return format_html(
                    '<a href="{}" style="color:#417690; text-decoration:none;">{}</a>',
                    url,
                    obj.import_source_load_number
                )
        except Exception:
            pass
        
        # Fallback: just display the load number
        return obj.import_source_load_number
    
    import_source_load_number_link.short_description = "Import Source Load Number"
    
    def custom_documents_display(self, obj):
        """Display ONLY custom/other documents section with document name input"""
        if not obj.pk:
            return "Save first"
        
        other_docs = obj.other_documents if obj.other_documents else []
        
        html = '<table style="width: 100%; border-collapse: collapse;">'
        
        # Display existing custom documents
        for idx, doc_cat in enumerate(other_docs):
            cat_name = doc_cat.get('name', 'Custom')
            files = doc_cat.get('files', [])
            
            html += '<tr style="border-bottom: 1px solid #e0e0e0;">'
            # Left column: Category name with remove button
            html += f'''<td style="padding: 10px 20px 10px 0; width: 150px; font-weight: 500; vertical-align: top;">
                <div>{cat_name}</div>
                <button type="button" 
                        class="other-remove-category" 
                        data-idx="{idx}"
                        style="background: #d32f2f; 
                               color: white; 
                               border: none; 
                               padding: 8px 16px; 
                               cursor: pointer; 
                               border-radius: 3px; 
                               font-size: 13px; 
                               font-weight: 500;
                               margin-top: 8px;
                               margin-left: 10px;
                               display: block;
                               min-width: 80px;">
                    Remove
                </button>
            </td>'''
            
            # Right column: Files with remove buttons
            html += '<td style="padding: 10px 0;">'
            html += f'<ul class="other-doc-list-{idx}" style="list-style: none; padding: 0; margin: 0 0 8px 0;">'
            
            for file in files:
                html += f'''
                <li class="other-doc-item" style="display: inline-block; margin-right: 15px; margin-bottom: 5px;">
                    <a href="/media/{file['file']}" target="_blank" style="color: #417690; font-size: 12px; text-decoration: none;">{file['filename']}</a>
                    <button type="button"
                            class="other-remove-file"
                            data-idx="{idx}"
                            data-file-id="{file['id']}"
                            style="margin-left: 5px; border: none; background: none; color: #d32f2f; font-weight: bold; cursor: pointer; font-size: 16px; padding: 0; line-height: 1;">×</button>
                </li>
                '''
            
            html += '</ul>'
            html += f'<div class="other-file-rows-{idx}" style="display:none;"></div>'
            html += f'''<button type="button" 
                    class="other-add-file" 
                    data-idx="{idx}"
                    style="background: #417690; 
                           color: white; 
                           border: none; 
                           padding: 6px 16px; 
                           cursor: pointer; 
                           border-radius: 3px; 
                           font-size: 12px; 
                           font-weight: 500; 
                           white-space: nowrap; 
                           min-width: 70px;
                           display: inline-block;">
                + Add
            </button>'''
            html += '</td></tr>'
        
        # New document row - always visible
        html += '''<tr style="border-bottom: 1px solid #e0e0e0;">
            <td style="padding: 15px 20px 15px 0; width: 150px; vertical-align: middle;">
                <input type="text" 
                       id="new-doc-name" 
                       placeholder="Document name" 
                       style="width: 130px; padding: 8px; border: 1px solid #ccc; border-radius: 3px; font-size: 12px;">
            </td>
            <td style="padding: 15px 0;">
                <button type="button" 
                        id="add-new-document"
                        style="background: #417690; 
                               color: white; 
                               border: none; 
                               padding: 8px 20px; 
                               cursor: pointer; 
                               border-radius: 3px; 
                               font-size: 13px; 
                               font-weight: 500; 
                               white-space: nowrap; 
                               min-width: 120px;
                               display: inline-block;">
                    + Add
                </button>
            </td>
        </tr>'''
        
        html += '</table>'
        
        return mark_safe(html)
    
    custom_documents_display.short_description = ""
    
    def has_add_permission(self, request):
        """Disable manual add - transport created automatically by billing signal"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Allow deletion (will be re-created if billing still marked dispatched)"""
        return super().has_delete_permission(request, obj)

class HQDeliverySiteAdmin(DeliverySiteAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).filter(site__isnull=True)

# ============================================================================
# REGISTER ALL MODELS WITH HQ ADMIN SITE
# ============================================================================

hq_admin_site.register(Site, HQSiteAdmin)
hq_admin_site.register(UserSite, HQUserSiteAdmin)

# Commercial
hq_admin_site.register(Client, HQClientAdmin)
hq_admin_site.register(CompanyDetails, HQCompanyDetailsAdmin)
hq_admin_site.register(Transporter, HQTransporterAdmin)
hq_admin_site.register(Warehouse, HQWarehouseAdmin)

# Compliance
hq_admin_site.register(PolicyCategory, HQPolicyCategoryAdmin)
hq_admin_site.register(SopsCategory, HQSopsCategoryAdmin)
hq_admin_site.register(PolicyComplianceDocument, HQPolicyComplianceDocumentAdmin)
hq_admin_site.register(ProductComplianceDocument, HQProductComplianceDocumentAdmin)
hq_admin_site.register(SopsComplianceDocument, HQSopsComplianceDocumentAdmin)
hq_admin_site.register(SpecSheet, HQSpecSheetAdmin)

# Costing
hq_admin_site.register(BillingDocumentHeader, HQBillingDocumentHeaderAdmin)

# Incident Management
hq_admin_site.register(Incident, HQIncidentAdmin)

# Inventory
hq_admin_site.register(PurchaseOrder, HQPurchaseOrderAdmin)

# Manufacturing
hq_admin_site.register(ManufacturingReport, HQManufacturingReportAdmin)

# Transport
hq_admin_site.register(TransportLoad, HQTransportLoadAdmin)
hq_admin_site.register(DeliverySite, HQDeliverySiteAdmin)
