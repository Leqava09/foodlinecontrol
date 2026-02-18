from django.db import models
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import path
from django.http import HttpResponse
from django.utils.safestring import mark_safe
from django.contrib import messages
from inventory.models import StockTransaction, StockItem
from product_details.models import ProductCategory, Product
from . import views
from django.core.exceptions import ValidationError
from .forms import ProductionForm, BatchForm, BatchFormSet

from .models import (
    Production, Batch, BatchContainer, Waste, MeatWaste, NSIDocument, 
    ProductionDateDocument, BatchProductInventoryUsed, ManufacturingReport, StockUsageReport
)
from foodlinecontrol.admin_base import ArchivableAdmin
from tenants.admin_utils import SiteAwareModelAdmin


# ============= VIEW FUNCTIONS =============

def product_usage_sheet_view(request, batch_id):
    batch = get_object_or_404(Batch, pk=batch_id)
    product = batch.product
    items = []

    if request.method == "POST":
        for key in request.POST:
            if key.startswith("qty_used_"):
                stockitem_id = key[len("qty_used_"):]
                try:
                    stock_item = StockItem.objects.get(id=stockitem_id)
                except StockItem.DoesNotExist:
                    continue
                
                qty_used = float(request.POST.get(f"qty_used_{stockitem_id}", 0) or 0)
                waste_qty = float(request.POST.get(f"waste_qty_{stockitem_id}", 0) or 0)
                batch_ref = request.POST.get(f"batch_ref_{stockitem_id}", "")
                
                BatchProductInventoryUsed.objects.update_or_create(
                    batch=batch,
                    stock_item=stock_item,
                    product=product,
                    defaults={
                        'qty_used': qty_used,
                        'waste_qty': waste_qty,
                        'ref_number': batch_ref,
                    }
                )
                
                StockTransaction.objects.update_or_create(
                    batch=batch,
                    stock_item=stock_item,
                    transaction_type="OUT",
                    batch_ref=batch_ref,
                    defaults={
                        'amount_used': qty_used,
                        'waste_per_production_batch': waste_qty,
                        'quantity': qty_used + waste_qty,
                        'category': stock_item.category,
                        'transaction_date': batch.production_date,
                    }
                )
        messages.success(request, "Product usage data saved successfully!")
        
        if "save_return" in request.POST:
            return redirect(reverse("admin:manufacturing_batch_change", args=[batch.pk]))

    for ing in product.components.all():
        stock_item = ing.stock_item
        standard_usage = getattr(ing, "standard_usage_per_production_unit", 0)
        supposed_usage = batch.shift_total * standard_usage if batch.shift_total and standard_usage else 0
        available = getattr(stock_item, "stock_level_display", "-")

        batch_usage = BatchProductInventoryUsed.objects.filter(
            batch=batch,
            stock_item=stock_item
        ).first()
        
        qty_used = batch_usage.qty_used if batch_usage else ""
        waste_qty = batch_usage.waste_qty if batch_usage else ""
        batch_ref = batch_usage.ref_number if batch_usage else ""

        available_batch_refs = StockTransaction.objects.filter(
            stock_item=stock_item,
            transaction_type='IN'
        ).values_list('batch_ref', flat=True).distinct().exclude(batch_ref='').exclude(batch_ref__isnull=True)

        items.append({
            "name": stock_item.name,
            "unit_of_measure": getattr(stock_item, "unit_of_measure", ""),
            "available": available,
            "stock_item": stock_item,
            "standard_usage": standard_usage,
            "supposed_usage": supposed_usage,
            "qty_used": qty_used,
            "waste_qty": waste_qty,
            "batch_ref": batch_ref,
            "available_batch_refs": list(available_batch_refs),
        })

    if hasattr(product, "packaging_items"):
        for pack in product.packaging_items.all():
            stock_item = pack.packaging
            standard_usage = getattr(pack, "standard_usage_per_production_unit", 0)
            supposed_usage = batch.shift_total * standard_usage if batch.shift_total and standard_usage else 0
            available = getattr(stock_item, "stock_level_display", "-")

            batch_usage = BatchProductInventoryUsed.objects.filter(
                batch=batch,
                stock_item=stock_item
            ).first()
            
            qty_used = batch_usage.qty_used if batch_usage else ""
            waste_qty = batch_usage.waste_qty if batch_usage else ""
            batch_ref = batch_usage.ref_number if batch_usage else ""

            available_batch_refs = StockTransaction.objects.filter(
                stock_item=stock_item,
                transaction_type='IN'
            ).values_list('batch_ref', flat=True).distinct().exclude(batch_ref='').exclude(batch_ref__isnull=True)

            items.append({
                "name": stock_item.name,
                "unit_of_measure": getattr(stock_item, "unit_of_measure", ""),
                "available": available,
                "stock_item": stock_item,
                "standard_usage": standard_usage,
                "supposed_usage": supposed_usage,
                "qty_used": qty_used,
                "waste_qty": waste_qty,
                "batch_ref": batch_ref,
                "available_batch_refs": list(available_batch_refs),
            })

    return render(
        request,
        "admin/manufacturing/product_usage_sheet.html",
        {
            'batch': batch,
            'product': product,
            'items': items,
            'shift_total': batch.shift_total,
        }
    )

# ============= INLINE CLASSES =============

class BatchContainerInline(admin.TabularInline):
    model = BatchContainer
    extra = 1
    autocomplete_fields = ['container']
    fields = ('container', 'kg_frozen_meat_used', 'frozen_meat_available')
    readonly_fields = ('frozen_meat_available',)
    verbose_name = "Container Used"
    verbose_name_plural = "Frozen Meat already used AND then also available"

    def frozen_meat_available(self, obj):
        if not obj.container_id or not hasattr(obj.container, "net_weight"):
            return "N/A"
        net_weight = obj.container.net_weight
        used_qs = BatchContainer.objects.filter(container=obj.container)
        if obj.pk:
            used_qs = used_qs.exclude(pk=obj.pk)
        used = used_qs.aggregate(total=models.Sum('kg_frozen_meat_used'))['total'] or 0
        total_used = used + (obj.kg_frozen_meat_used or 0)
        available = net_weight - total_used
        return f"{available:,.2f} kg"
    frozen_meat_available.short_description = "Frozen Meat Available (kg)"

    class Media:
        js = ('admin/js/batch_admin.js',)


class NSIDocumentInline(admin.TabularInline):
    model = NSIDocument
    extra = 0
    fields = ['file', 'uploaded_at']
    readonly_fields = ['uploaded_at']


class WasteInline(admin.TabularInline):
    model = Waste
    extra = 0
    fields = (
        'machine_count', 'seal_creeps', 'unsealed_poor_seal', 'screwed_and_undated',
        'over_weight', 'under_weight', 'empty_pouches', 'metal_detection', 'machine_waste_total',
        'retort_count', 'damage_boxes', 'unclear_coding', 'retort_seal_creap',
        'retort_under_weight', 'poor_ceiling_destroyed', 'retort_waste_total',
        'pouches_withdrawn', 'total_returned', 'balance_pouches', 'packed', 'nsi_sample_pouches'
    )
    readonly_fields = ('machine_waste_total', 'retort_waste_total', 'balance_pouches', 'production_date')
    verbose_name = "Pouch Waste Record"
    verbose_name_plural = "Pouch Waste Records"


class MeatWasteInline(admin.TabularInline):
    model = MeatWaste
    extra = 0
    fields = ('total_meat_defrosted', 'meat_waste', 'production_date')
    readonly_fields = ('production_date',)
    verbose_name = "Meat Waste Record"
    verbose_name_plural = "Meat Waste Records"

class BatchInline(admin.TabularInline):
    model = Batch
    form = BatchForm
    formset = BatchFormSet
    extra = 0
    fields = ('a_no', 'batch_number', 'category', 'product', 'sku', 'size', 'shift_total')
    readonly_fields = ('size',)
    can_delete = True
    
    def get_form(self, request, obj=None, **kwargs):
        """Get form and configure site-aware filtering"""
        form = super().get_form(request, obj, **kwargs)
        
        # Get the site from request context
        site = getattr(request, 'current_site', None)
        
        # Set base_fields queryset for the entire form class
        if site:
            print(f'[BatchInline.get_form] Setting site-filtered querysets for: {site}')
            form.base_fields['category'].queryset = ProductCategory.objects.filter(site=site)
            form.base_fields['product'].queryset = Product.objects.filter(site=site)
            print(f'[BatchInline.get_form] Category count: {form.base_fields["category"].queryset.count()}')
            print(f'[BatchInline.get_form] Product count: {form.base_fields["product"].queryset.count()}')
        else:
            print('[BatchInline.get_form] No current_site found in request')
        
        return form
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter category and product by current site"""
        if db_field.name == 'category':
            # Get the site from request
            if hasattr(request, 'current_site') and request.current_site:
                kwargs['queryset'] = ProductCategory.objects.filter(site=request.current_site)
                print(f'[BatchInline] Filtered category by site: {request.current_site}')
        elif db_field.name == 'product':
            # Filter products by current site
            if hasattr(request, 'current_site') and request.current_site:
                kwargs['queryset'] = Product.objects.filter(site=request.current_site)
                print(f'[BatchInline] Filtered product by site: {request.current_site}')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    def save_model(self, request, obj, form, change):
        """Ensure full_clean is called before saving"""
        try:
            obj.full_clean()
        except Exception:
            pass  # Allow save even if clean fails, we'll show error messages
        super().save_model(request, obj, form, change)
    
    class Media:
        js = ('js/batch_inline_sku_size.js', 'js/batch_inline_delete.js')
        css = {'all': ('css/batch_inline.css',)}

# ============= BATCH ADMIN =============

#@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    form = BatchForm
    inlines = [BatchContainerInline, NSIDocumentInline, WasteInline, MeatWasteInline]
    
    readonly_fields = (
        'expiry_date',
        'estimated_dispatch_date',
        'product_usage_sheet_button',
        'horizontal_buttons',
    )

    list_display = (
        'display_production_date',
        'a_no',
        'batch_number',
        'get_product_name',
        'size',
        'shift_total',
        'status',
        'display_estimated_dispatch_date',
    )

    fieldsets = (
        ('Production Information', {
            'fields': (
                'production_date',
                'a_no',
                'batch_number',
                'expiry_date',
                'product',  
                'size',
                'shift_total',
                'horizontal_buttons',
            )
        }),
        ('Incubation & Certification', {
            'fields': (
                'incubation_start',
                'incubation_end',
                'certification_date',
                ('dispatch_date', 'estimated_dispatch_date'),
                'status',
                'nsi_submission_date',
            )
        }),
    )

    def display_production_date(self, obj):
        return obj.production_date.strftime("%d/%m/%Y") if obj.production_date else ""
    display_production_date.short_description = "Production Date"

    def get_product_name(self, obj):
        return obj.product.product_name if obj.product else "-"
    get_product_name.short_description = "Product Name"

    def display_estimated_dispatch_date(self, obj):
        if obj.production_date:
            return (obj.production_date + timedelta(days=17)).strftime("%d/%m/%Y")
        return ""
    display_estimated_dispatch_date.short_description = "Estimated Dispatch Date"

    def product_usage_sheet_button(self, obj):
        if not obj.pk:
            return ""
        url = reverse("admin:batch_usage", args=[obj.pk])
        return mark_safe(
            f'<a class="button" style="margin-right:10px;" href="{url}" target="_blank">Product Usage Sheet</a>'
        )
    product_usage_sheet_button.short_description = "Product Usage Sheet"

    def horizontal_buttons(self, obj):
        return mark_safe(
            f"""
            <div style="text-align:right;">
                <a class="grp-button grp-default" href="{reverse('admin:batch_usage', args=[obj.pk])}">Product Usage Sheet</a>
            </div>
            """
        )
    horizontal_buttons.short_description = "Batch Reporting"

    def estimated_dispatch_date(self, obj):
        if obj.production_date:
            return obj.production_date + timedelta(days=17)
        return "N/A"
    estimated_dispatch_date.short_description = "Estimated Dispatch Date (+17 days)"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<path:batch_id>/product-usage-sheet/',
                self.admin_site.admin_view(product_usage_sheet_view),
                name='batch_usage',
            ),
        ]
        return custom_urls + urls
    
    def save_model(self, request, obj, form, change):
        if obj.product and hasattr(obj.product, 'size'):
            obj.size = obj.product.size or ''
        else:
            obj.size = ''
        super().save_model(request, obj, form, change)
    
        
# ============= PRODUCTION ADMIN (NEW) =============

@admin.register(Production)
class ProductionAdmin(SiteAwareModelAdmin, ArchivableAdmin):
    form = ProductionForm
    inlines = [BatchInline]
    change_list_template = 'admin/manufacturing/production_changelist.html'
    
    list_display = ('display_production_date',)
    
    def has_delete_permission(self, request):
        """Hide Delete button from form - only allow deletion from list view"""
        return False
    
    def history_view(self, request, object_id, extra_context=None):
        """Override to show ALL history entries (no limit)"""
        from django.contrib.admin.models import LogEntry
        from django.contrib.contenttypes.models import ContentType
        
        # Get all log entries for this object (no limit)
        content_type = ContentType.objects.get_for_model(self.model)
        action_list = LogEntry.objects.filter(
            object_id=object_id,
            content_type=content_type
        ).select_related().order_by('-action_time')
        
        extra_context = extra_context or {}
        extra_context['action_list'] = action_list
        
        return super().history_view(request, object_id, extra_context=extra_context)
    
    search_fields = ['production_date']
    
    # ✅ CHANGE: Remove expiry_date_display from here
    fieldsets = (
        ('Production Information', {
            'fields': (
                'production_date',
            )
        }),
        ('Batch Details', {
            'fields': ('waste_buttons',)  
        }),
    )

    readonly_fields = ('waste_buttons',)

    def display_production_date(self, obj):
        return obj.production_date.strftime("%d/%m/%Y")
    display_production_date.short_description = "Production Date"
    
    def save_model(self, request, obj, form, change):
        from dateutil.relativedelta import relativedelta
        if obj.production_date:
            obj.expiry_date = obj.production_date + relativedelta(years=3)
        super().save_model(request, obj, form, change)
   
    class Media:
        js = ('js/production_expiry.js', 'js/batch_inline_delete.js')
        css = {'all': ('css/batch_inline.css',)}

    def expiry_date_display(self, obj):
        """Display expiry date calculated from production date (read-only)"""
        if obj and obj.production_date:
            from dateutil.relativedelta import relativedelta
            expiry = obj.production_date + relativedelta(years=3)
            return expiry.strftime("%d/%m/%Y")
        return "-"
    expiry_date_display.short_description = "Expiry Date"
   
    def save_formset(self, request, form, formset, change):
        ...
        instances = formset.save(commit=False)
        for instance in instances:
            if isinstance(instance, Batch):
                instance.production_date = form.instance.production_date
                instance.site = form.instance.site  # ✅ CRITICAL: Set site from parent Production

                # copy live product size into batch.size
                if instance.product and hasattr(instance.product, 'size'):
                    instance.size = instance.product.size or ''
                else:
                    instance.size = ''

            instance.save()
        formset.save_m2m()

       
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('batch/<str:site_slug>/<str:production_date>/detail/', views.production_batch_detail_view, name='batch_detail'),
        ]
        return custom_urls + urls    
    
    def waste_buttons(self, obj):
        """Display button to access Production Batch Detail with 4 tabs"""
        if not obj or not obj.production_date:
            return "Save production date first"
        
        batch = Batch.objects.filter(production_date=obj.production_date, site=obj.site).first()
        if not batch:
            return "No batch found"
        
        # Use site slug and production_date in YYYYMMDD format
        date_str = obj.production_date.strftime('%Y%m%d')
        site_slug = obj.site.slug if obj.site else 'default'
        url = f"/manufacturing/batch/{site_slug}/{date_str}/detail/"  # ✅ Site-specific URL
        html = f'<a class="button" href="{url}">📊 Batch Details - All Forms</a>'
        return mark_safe(html)
    
    def a_no(self, obj):
        batch = Batch.objects.filter(production_date=obj.production_date, site=obj.site).first()
        return batch.a_no if batch else "-"
    a_no.short_description = "A-NO"
    
    def batch_number(self, obj):
        batch = Batch.objects.filter(production_date=obj.production_date, site=obj.site).first()
        return batch.batch_number if batch else "-"
    batch_number.short_description = "Production Code"
    
    def product_name(self, obj):
        batch = Batch.objects.filter(production_date=obj.production_date, site=obj.site).first()
        return batch.product.product_name if batch and batch.product else "-"
    product_name.short_description = "Product Name"
    
    def size(self, obj):
        batch = Batch.objects.filter(production_date=obj.production_date, site=obj.site).first()
        return batch.size if batch else "-"
    size.short_description = "Size of Pouch"
    
    def shift_total(self, obj):
        batch = Batch.objects.filter(production_date=obj.production_date).first()
        return batch.shift_total if batch else "-"
    shift_total.short_description = "Shift Total"
    
    def has_delete_permission(self, request, obj=None):
        return True

    def get_submit_line_html(self):
        """Override submit line to add Home and Delete buttons"""
        from django.utils.html import format_html
        return format_html(
            '<div class="submit-row">'
            '<a href="/admin/" class="button" style="background-color: #417690;">🏠 Home</a>'
            '<div style="margin-left: auto; display: flex; gap: 10px;">'
            '{}'
            '</div></div>',
            super().get_submit_line_html()
        )

    def all_batches_list(self, obj):
        """Display all batches for this production date"""
        batches = Batch.objects.filter(production_date=obj.production_date, site=obj.site)
        if not batches:
            return "No batches"
        
        batch_info = []
        for batch in batches:
            batch_info.append(f"{batch.a_no} - {batch.batch_number} - {batch.product.product_name if batch.product else '-'}")
        return " | ".join(batch_info)
    all_batches_list.short_description = "Batches"

    def batch_count(self, obj):
        return Batch.objects.filter(production_date=obj.production_date, site=obj.site).count()
    batch_count.short_description = "# Batches"

    def a_nos_list(self, obj):
        batches = Batch.objects.filter(production_date=obj.production_date, site=obj.site).values_list('a_no', flat=True)
        return " | ".join(batches) if batches else "-"
    a_nos_list.short_description = "A-NOs"

    def batch_numbers_list(self, obj):
        batches = Batch.objects.filter(production_date=obj.production_date, site=obj.site).values_list('batch_number', flat=True)
        return " | ".join(batches) if batches else "-"
    batch_numbers_list.short_description = "Batch Numbers"

    def product_names_list(self, obj):
        products = set()
        for batch in Batch.objects.filter(production_date=obj.production_date, site=obj.site):
            if batch.product:
                products.add(batch.product.product_name)
        return ", ".join(products)
    product_names_list.short_description = "Products"
    

# ============= MANUFACTURING REPORT ADMIN =============
from django.db.models import Sum, Count
from django.template.response import TemplateResponse


@admin.register(ManufacturingReport)
class ManufacturingReportAdmin(admin.ModelAdmin):
    """
    Read-only report view showing manufacturing status summary.
    """
    change_list_template = 'admin/manufacturing/manufacturingreport/change_list.html'
    
    # Disable add/change/delete
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def changelist_view(self, request, extra_context=None):
        """Custom changelist that shows aggregated certification data."""
        from datetime import date, timedelta
        from django.db.models import Q
        from decimal import Decimal
        from tenants.models import Site
        
        # Get filter values from request
        status_filter = request.GET.get('status', '')
        date_from = request.GET.get('date_from', '')
        date_to = request.GET.get('date_to', '')
        site_filter = request.GET.get('site', '')  # NEW: site filter
        
        # Get current site from session
        site_id = request.session.get('current_site_id')
        is_hq_context = request.session.get('is_hq_context', False)
        
        # Base queryset - exclude archived and failed, filter by site
        queryset = Batch.objects.filter(
            production__is_archived=False
        ).exclude(
            status__in=['Failed Drainmass', 'Failed 37°C Micro Test', 'Failed 55°C Micro Test']
        ).select_related('product', 'production', 'site')
        
        # Filter by site based on context
        if is_hq_context and site_filter:
            # HQ context with site filter selected
            queryset = queryset.filter(site_id=site_filter)
        elif site_id and not is_hq_context:
            # Site-specific context - always filter by that site
            queryset = queryset.filter(site_id=site_id)
        elif is_hq_context and not site_filter:
            # HQ context with no site selected - show all sites
            pass
        
        # Apply filters
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        if date_from:
            try:
                from datetime import datetime
                df = datetime.strptime(date_from, '%Y-%m-%d').date()
                queryset = queryset.filter(certification_date__gte=df)
            except:
                pass
        
        if date_to:
            try:
                from datetime import datetime
                dt = datetime.strptime(date_to, '%Y-%m-%d').date()
                queryset = queryset.filter(certification_date__lte=dt)
            except:
                pass
        
        # Get all batches with ready_dispatch calculated
        all_batches = []
        total_shift = Decimal('0')
        total_ready = Decimal('0')
        
        for batch in queryset.order_by('production_date', 'batch_number'):
            ready_dispatch = batch.get_ready_to_dispatch()
            batch.ready_dispatch = ready_dispatch
            all_batches.append(batch)
            total_shift += Decimal(str(batch.shift_total or 0))
            total_ready += Decimal(str(ready_dispatch or 0))
        
        # Summary by status with ready_dispatch totals
        # Normalize status to handle case inconsistencies
        status_summary_dict = {}
        for batch in all_batches:
            # Normalize status to title case for display consistency
            status = batch.status
            # Map any case variations to the proper choice value
            status_map = {s[0].lower(): s[0] for s in Batch.STATUS_CHOICES}
            normalized_status = status_map.get(status.lower(), status)
            
            # Add display_status (replace underscores with spaces and title case)
            batch.display_status = normalized_status.replace('_', ' ').title()
            
            if normalized_status not in status_summary_dict:
                status_summary_dict[normalized_status] = {
                    'status': normalized_status,
                    'display_status': normalized_status.replace('_', ' ').title(),
                    'batch_count': 0,
                    'total_shift': Decimal('0'),
                    'total_ready': Decimal('0'),
                }
            status_summary_dict[normalized_status]['batch_count'] += 1
            status_summary_dict[normalized_status]['total_shift'] += Decimal(str(batch.shift_total or 0))
            status_summary_dict[normalized_status]['total_ready'] += Decimal(str(batch.ready_dispatch or 0))
        
        status_summary = sorted(status_summary_dict.values(), key=lambda x: x['status'])
        
        # Upcoming certifications (next 7 days)
        today = date.today()
        next_week = today + timedelta(days=7)
        upcoming = [b for b in all_batches if 
            b.certification_date and 
            b.certification_date >= today and 
            b.certification_date <= next_week and
            b.status in ['In Incubation', 'Awaiting Certification']
        ]
        
        # Awaiting certification details
        awaiting = [b for b in all_batches if b.status == 'Awaiting Certification']
        
        # In incubation details
        in_incubation = [b for b in all_batches if b.status == 'In Incubation']
        
        # Status choices for filter dropdown
        status_choices = Batch.STATUS_CHOICES
        
        # Get all sites for the site filter dropdown (only show in HQ context)
        site_choices = []
        if is_hq_context:
            site_choices = Site.objects.filter(is_active=True, is_archived=False).order_by('name').values_list('id', 'name')
        
        context = {
            **self.admin_site.each_context(request),
            'title': 'Certification Report',
            'status_summary': status_summary,
            'all_batches': all_batches,
            'total_shift': total_shift,
            'total_ready': total_ready,
            'upcoming': upcoming,
            'awaiting': awaiting,
            'in_incubation': in_incubation,
            'status_choices': status_choices,
            'site_choices': site_choices,  # NEW: site choices
            'current_status': status_filter,
            'current_site_filter': site_filter,  # NEW: current site filter
            'is_hq_context': is_hq_context,  # NEW: flag to show site filter in template
            'date_from': date_from,
            'date_to': date_to,
            'today': today,
            'opts': self.model._meta,
        }
        
        return TemplateResponse(
            request,
            self.change_list_template,
            context
        )


@admin.register(StockUsageReport)
class StockUsageReportAdmin(admin.ModelAdmin):
    """
    Read-only report view showing main stock item (Meat/Beans) usage.
    Shows container batch ref, book in qty, loss percentages, and totals.
    """
    change_list_template = 'admin/manufacturing/stockusagereport/change_list.html'
    
    # Disable add/change/delete
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def changelist_view(self, request, extra_context=None):
        """Custom changelist that shows stock usage data with loss calculations."""
        from datetime import date, timedelta
        from django.db.models import Sum, Avg, F, Q
        from decimal import Decimal
        from inventory.models import Container, StockTransaction, StockCategory
        from product_details.models import MainProductComponent
        
        # Get filter values from request
        category_filter = request.GET.get('category', '')
        container_filter = request.GET.get('container', '')
        date_from = request.GET.get('date_from', '')
        date_to = request.GET.get('date_to', '')
        
        # Get current site from session
        site_id = request.session.get('current_site_id')
        
        # Base queryset - all BatchContainer records (production usage), filtered by site
        queryset = BatchContainer.objects.select_related(
            'container', 'container__stock_item', 'container__stock_item__category'
        ).filter(
            Q(container__isnull=False) | Q(batch_ref__isnull=False)
        ).order_by('-production_date', 'container__container_number')
        
        # Filter by site if in site admin context
        # Use production_date to join with Batch model to get site
        if site_id:
            from manufacturing.models import Batch
            batch_pks = Batch.objects.filter(site_id=site_id).values_list('production_date', flat=True).distinct()
            queryset = queryset.filter(production_date__in=batch_pks)
        
        # Get MainProductComponent stock items for this site (DYNAMICALLY)
        main_product_components = MainProductComponent.objects.filter(
            product__site_id=site_id
        ).select_related('stock_item', 'category')
        
        main_stock_item_ids = set(mpc.stock_item_id for mpc in main_product_components)
        
        # Get unique categories from MainProductComponent items (DYNAMICALLY from actual components)
        main_categories_set = set()
        for mpc in main_product_components:
            if mpc.category:
                main_categories_set.add(mpc.category.name)
        main_categories = sorted(list(main_categories_set))
        
        # DO NOT filter here - we need to check BOTH containers AND local items (batch_ref)
        # Filter will happen in the loop for both types
        queryset_filtered = queryset
        
        # Apply filters - but keep both containers and batch_ref items
        if category_filter:
            # Only filter containers by category - local items filtered in loop
            queryset_filtered = queryset_filtered.filter(
                Q(container__stock_item__category__name__iexact=category_filter) |
                Q(batch_ref__isnull=False)  # Keep local items to check in loop
            )
        
        if container_filter:
            queryset_filtered = queryset_filtered.filter(
                Q(container__container_number__icontains=container_filter) |
                Q(batch_ref__icontains=container_filter)
            )
        
        if date_from:
            try:
                from datetime import datetime
                df = datetime.strptime(date_from, '%Y-%m-%d').date()
                queryset_filtered = queryset_filtered.filter(production_date__gte=df)
            except:
                pass
        
        if date_to:
            try:
                from datetime import datetime
                dt = datetime.strptime(date_to, '%Y-%m-%d').date()
                queryset_filtered = queryset_filtered.filter(production_date__lte=dt)
            except:
                pass
        
        # Process data - group by container
        container_data = {}
        daily_data = []
        
        # Import models for lookups
        from inventory.models import StockTransaction
        from manufacturing.models import MeatProductionSummary
        
        for bc in queryset_filtered:
            container_num = bc.container.container_number if bc.container else bc.batch_ref
            category_name = ''
            stock_item_name = ''
            stock_item_id = None
            book_in_qty = Decimal('0')
            total_cost = Decimal('0')
            price_per_kg = Decimal('0')
            source_type = bc.source_type or 'import'
            
            if bc.container:
                # Imported item - check if this container's stock_item is a MainProductComponent
                stock_item_id = bc.container.stock_item_id
                if stock_item_id not in main_stock_item_ids:
                    # Skip - not a MainProductComponent
                    continue
                
                category_name = bc.container.stock_item.category.name if bc.container.stock_item and bc.container.stock_item.category else ''
                stock_item_name = bc.container.stock_item.name if bc.container.stock_item else ''
                book_in_qty = bc.container.net_weight or Decimal('0')
                total_cost = bc.container.total_cost_nad or Decimal('0')
            else:
                # Local item - lookup from StockTransaction by batch_ref (get the Booking IN record)
                stock_tx = StockTransaction.objects.filter(
                    batch_ref__iexact=bc.batch_ref,
                    transaction_type='IN'
                ).select_related('category', 'stock_item').first()
                
                if stock_tx:
                    stock_item_id = stock_tx.stock_item_id if stock_tx.stock_item else None
                    # Check if this stock_item is a MainProductComponent for our site
                    if stock_item_id not in main_stock_item_ids:
                        # Skip this record - it's not a MainProductComponent
                        continue
                    
                    category_name = stock_tx.category.name if stock_tx.category else 'Local'
                    stock_item_name = stock_tx.stock_item.name if stock_tx.stock_item else (bc.batch_ref or '-')
                    # Use booking_in_total_qty (Total Amount) - this is the calculated field from kg_per_box * total_boxes
                    book_in_qty = stock_tx.booking_in_total_qty if stock_tx.booking_in_total_qty else (stock_tx.quantity or Decimal('0'))
                    # Calculate total cost from invoice + transport for price/kg
                    invoice = Decimal(str(stock_tx.total_invoice_amount_excl or 0))
                    transport = Decimal(str(stock_tx.transport_cost or 0))
                    total_cost = invoice + transport
                else:
                    # Skip - can't find stock transaction info
                    continue
            
            # Calculate loss percentages
            book_out = bc.book_out_qty or Decimal('0')
            stock_left = bc.stock_left or Decimal('0')
            kg_used = bc.kg_frozen_meat_used or Decimal('0')
            meat_filled = bc.meat_filled or Decimal('0')
            
            # Get balance_prev from PREVIOUS production date's stock_left (not stored field)
            # This matches how the form dynamically calculates/displays it
            balance_prev = Decimal('0')
            prev_container = BatchContainer.objects.filter(
                production_date__lt=bc.production_date,
                container=bc.container
            ).order_by('-production_date').first() if bc.container else None
            
            if not prev_container and bc.batch_ref:
                # For local items, lookup by batch_ref
                prev_container = BatchContainer.objects.filter(
                    production_date__lt=bc.production_date,
                    batch_ref=bc.batch_ref
                ).order_by('-production_date').first()
            
            if prev_container:
                balance_prev = prev_container.stock_left or Decimal('0')
            
            # Used Defrosted/Fresh = Balance from prev + Book out - Stock left
            used_defrosted = balance_prev + book_out - stock_left
            
            # % Loss from Frozen/Raw - Filling = Use stored waste_factor from BatchContainer
            # This is the same value shown on the production page
            loss_from_frozen_filling = Decimal(str(bc.waste_factor or 0))
            
            # % Loss from Frozen/Raw - Pouch Actual
            # This is calculated from MeatProductionSummary for the day
            # Formula: ((totalDefrosted - expectedOutput) / totalDefrosted) * 100
            # where expectedOutput = totalShiftQty * fillingWeightPerPouch
            loss_from_frozen_pouch = Decimal('0')
            try:
                # Get the site from container or batch
                item_site = None
                if bc.container:
                    item_site = bc.container.site
                else:
                    # For batch_ref, get the site from batch
                    batch = Batch.objects.filter(production_date=bc.production_date, batch_number=bc.batch_ref).first()
                    item_site = batch.site if batch else None
                
                meat_summary = MeatProductionSummary.objects.filter(
                    production_date=bc.production_date,
                    site=item_site
                ).first()
                if meat_summary and meat_summary.total_meat_filled:
                    filling_weight = meat_summary.filling_weight_per_pouch or Decimal('0.277')
                    # Get total pouches from all batches for this day and site
                    day_batches = Batch.objects.filter(production_date=bc.production_date, site=item_site)
                    total_shift_qty = sum(b.shift_total or 0 for b in day_batches)
                    expected_output = Decimal(str(total_shift_qty)) * filling_weight
                    # Get total defrosted for the day and site
                    day_containers = BatchContainer.objects.filter(production_date=bc.production_date)
                    if item_site:
                        # Filter by site - through container.site or batch.site
                        day_containers = day_containers.filter(
                            models.Q(container__site=item_site) |
                            models.Q(batch_ref__isnull=False)  # Keep local items
                        )
                    total_defrosted = sum((c.balance_from_prev_shift or 0) + (c.book_out_qty or 0) - (c.stock_left or 0) for c in day_containers)
                    if total_defrosted > 0:
                        loss_from_frozen_pouch = ((Decimal(str(total_defrosted)) - expected_output) / Decimal(str(total_defrosted))) * 100
            except:
                pass
            
            # Add display_category (remove underscores)
            display_category = category_name.replace('_', ' ')
            
            # Get production batches for this date
            from manufacturing.models import Batch
            production_batches = Batch.objects.filter(production_date=bc.production_date).select_related('product')
            batch_info = []
            for batch in production_batches:
                batch_info.append({
                    'batch_number': batch.batch_number,
                    'product': str(batch.product) if batch.product else '-',
                    'size': batch.size if hasattr(batch, 'size') and batch.size else '-',
                    'shift_total': batch.shift_total or 0,
                })
            
            daily_row = {
                'production_date': bc.production_date,
                'container_number': container_num,
                'category': category_name,
                'display_category': display_category,
                'stock_item': stock_item_name,
                'book_in_qty': book_in_qty,
                'balance_prev': balance_prev,
                'book_out_qty': book_out,
                'stock_left': stock_left,
                'used_defrosted': used_defrosted,
                'kg_used': kg_used,
                'meat_filled': meat_filled,
                'loss_from_frozen_filling': loss_from_frozen_filling,
                'loss_from_frozen_pouch': loss_from_frozen_pouch,
                'production_batches': batch_info,
            }
            daily_data.append(daily_row)
            
            # Aggregate by container
            if container_num not in container_data:
                container_data[container_num] = {
                    'container_number': container_num,
                    'category': category_name,
                    'display_category': display_category,
                    'stock_item': stock_item_name,
                    'book_in_qty': book_in_qty,
                    'total_cost': total_cost,
                    'total_book_out': Decimal('0'),
                    'total_used_defrosted': Decimal('0'),
                    'total_meat_filled': Decimal('0'),
                    'usage_count': 0,
                    'production_dates': [],
                    'batch_details': [],  # Store individual batch usage details
                    'loss_filling_values': [],  # Collect all loss filling values
                    'loss_pouch_values': [],  # Collect all loss pouch values
                }
            
            container_data[container_num]['total_book_out'] += book_out
            container_data[container_num]['total_used_defrosted'] += used_defrosted
            container_data[container_num]['total_meat_filled'] += meat_filled
            container_data[container_num]['usage_count'] += 1
            container_data[container_num]['loss_filling_values'].append(loss_from_frozen_filling)
            container_data[container_num]['loss_pouch_values'].append(loss_from_frozen_pouch)
            if bc.production_date not in container_data[container_num]['production_dates']:
                container_data[container_num]['production_dates'].append(bc.production_date)
            
            # Add this batch's details to the container
            container_data[container_num]['batch_details'].append({
                'production_date': bc.production_date,
                'balance_prev': balance_prev,
                'book_out_qty': book_out,
                'stock_left': stock_left,
                'used_defrosted': used_defrosted,
                'meat_filled': meat_filled,
                'loss_filling': loss_from_frozen_filling,
                'loss_pouch': loss_from_frozen_pouch,
                'production_batches': batch_info,  # Add batch info to expandable details
            })
        
        # Calculate container-level loss percentages
        container_summary = []
        for container_num, data in container_data.items():
            total_book_out = data['total_book_out']
            total_used = data['total_used_defrosted']
            total_filled = data['total_meat_filled']
            book_in = data['book_in_qty']
            
            # Use average of the stored loss values from production
            avg_loss_filling = Decimal('0')
            avg_loss_pouch = Decimal('0')
            remaining_stock = Decimal('0')
            
            if data['loss_filling_values']:
                avg_loss_filling = sum(data['loss_filling_values']) / len(data['loss_filling_values'])
            if data['loss_pouch_values']:
                avg_loss_pouch = sum(data['loss_pouch_values']) / len(data['loss_pouch_values'])
            
            # Remaining stock = Book in - Total booked out
            remaining_stock = book_in - total_book_out
            
            # Price per unit
            price_per_kg = Decimal('0')
            if book_in > 0 and data['total_cost'] > 0:
                price_per_kg = data['total_cost'] / book_in
            
            # Sort batch_details by production_date ascending (oldest first)
            sorted_batch_details = sorted(data['batch_details'], key=lambda x: x['production_date'])
            
            # Add used_costing to each batch detail (used × price/kg)
            for bd in sorted_batch_details:
                bd['used_costing'] = bd['used_defrosted'] * price_per_kg
            
            container_summary.append({
                **data,
                'batch_details': sorted_batch_details,  # Use sorted details
                'avg_loss_filling': avg_loss_filling,
                'avg_loss_pouch': avg_loss_pouch,
                'remaining_stock': remaining_stock,
                'price_per_kg': price_per_kg,
            })
        
        # Sort container summary
        container_summary = sorted(container_summary, key=lambda x: x['container_number'])
        
        # Calculate grand totals
        grand_totals = {
            'total_book_in': sum(c['book_in_qty'] for c in container_summary),
            'total_book_out': sum(c['total_book_out'] for c in container_summary),
            'total_used': sum(c['total_used_defrosted'] for c in container_summary),
            'total_filled': sum(c['total_meat_filled'] for c in container_summary),
            'total_remaining': sum(c['remaining_stock'] for c in container_summary),
            'total_cost': sum(c['total_cost'] for c in container_summary),
        }
        
        # Overall loss percentages - use average of container loss values
        all_filling_losses = [c['avg_loss_filling'] for c in container_summary if c['avg_loss_filling'] > 0]
        all_pouch_losses = [c['avg_loss_pouch'] for c in container_summary if c['avg_loss_pouch'] > 0]
        
        if all_filling_losses:
            grand_totals['overall_loss_filling'] = sum(all_filling_losses) / len(all_filling_losses)
        else:
            grand_totals['overall_loss_filling'] = Decimal('0')
        
        if all_pouch_losses:
            grand_totals['overall_loss_pouch'] = sum(all_pouch_losses) / len(all_pouch_losses)
        else:
            grand_totals['overall_loss_pouch'] = Decimal('0')
        
        # Use the main_categories we already computed for the filter dropdown
        category_choices = main_categories
        
        # Get company currency
        from commercial.models import CompanyDetails
        company = CompanyDetails.objects.first()
        currency = company.currency if company and company.currency else 'NAD'
        
        today = date.today()
        
        context = {
            **self.admin_site.each_context(request),
            'title': 'Stock Usage Report',
            'daily_data': daily_data,
            'container_summary': container_summary,
            'grand_totals': grand_totals,
            'category_choices': category_choices,
            'current_category': category_filter,
            'current_container': container_filter,
            'date_from': date_from,
            'date_to': date_to,
            'today': today,
            'currency': currency,
            'opts': self.model._meta,
        }
        
        return TemplateResponse(
            request,
            self.change_list_template,
            context
        )
