from django import forms
from django.core.exceptions import ValidationError
from django.template.response import TemplateResponse
from django.contrib.admin import helpers as admin_helpers
from django.utils.translation import gettext_lazy as _
from django.contrib import admin, messages
from django.contrib.admin import widgets as admin_widgets
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.urls import path
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.safestring import mark_safe
from django.utils.http import urlencode
from django.forms import HiddenInput
from django.db.models import Sum
from decimal import Decimal
from datetime import date
import json
from itertools import groupby
from operator import attrgetter
from .models import Container, StockItem, StockTransaction, Amendment, StockCategory, StockSubCategory, UnitOfMeasure, FinishedProductTransaction, Batch, PickingSlip
from inventory.models import StockTransaction, Amendment, StockCategory
from commercial.models import Supplier, Warehouse
from manufacturing.models import Batch, BatchProductInventoryUsed, BatchContainer, Sauce
from product_details.models import ProductComponent
from manufacturing.views import get_production_usage_data_for_inventory
from foodlinecontrol.admin_base import ArchivableAdmin
from tenants.admin_utils import SiteAwareModelAdmin

class DisabledSelect(forms.Select):
    def render(self, name, value, attrs=None, renderer=None):
        attrs = attrs or {}
        attrs['disabled'] = 'disabled'
        return super().render(name, value, attrs, renderer)

class AmendmentInline(admin.TabularInline):
    model = Amendment
    extra = 1
    
from commercial.models import Supplier
from .models import Container

class ContainerAdmin(SiteAwareModelAdmin, admin.ModelAdmin):
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter foreign key dropdowns by site"""
        current_site = getattr(request, 'current_site', None)
        
        if db_field.name == "supplier":
            from commercial.models import Supplier
            if current_site:
                kwargs["queryset"] = Supplier.objects.filter(site_id=current_site.id)
            else:
                kwargs["queryset"] = Supplier.objects.all()
        elif db_field.name == "warehouse":
            from commercial.models import Warehouse
            if current_site:
                kwargs["queryset"] = Warehouse.objects.filter(site_id=current_site.id)
            else:
                kwargs["queryset"] = Warehouse.objects.all()
        elif db_field.name == "stock_item":
            from .models import StockItem
            if current_site:
                kwargs["queryset"] = StockItem.objects.filter(site_id=current_site.id)
            else:
                kwargs["queryset"] = StockItem.objects.all()
        elif db_field.name == "item_category":
            from .models import StockCategory
            if current_site:
                kwargs["queryset"] = StockCategory.objects.filter(site_id=current_site.id)
            else:
                kwargs["queryset"] = StockCategory.objects.all()
        elif db_field.name == "sub_category":
            from .models import StockSubCategory
            if current_site:
                kwargs["queryset"] = StockSubCategory.objects.filter(site_id=current_site.id)
            else:
                kwargs["queryset"] = StockSubCategory.objects.all()
        
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    class ContainerAdminForm(forms.ModelForm):
        class Meta:
            model = Container
            fields = '__all__'
        
        def clean_container_number(self):
            container_number = self.cleaned_data.get('container_number')
            if container_number:
                # Check if a StockTransaction IN already exists with this batch_ref
                existing_tx = StockTransaction.objects.filter(
                    batch_ref=container_number, transaction_type='IN'
                ).exists()
                if existing_tx:
                    raise forms.ValidationError(
                        f"A Local Book In transaction already exists for batch reference '{container_number}'. "
                        f"Only one Booking In is allowed per batch."
                    )
            return container_number
    
    form = ContainerAdminForm
    
    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['title'] = 'Import Book In'
        
        # Store back_url in context and session for navigation
        back_url = request.GET.get('next', '') or request.GET.get('back_url', '')
        if back_url:
            extra_context['back_url'] = back_url
            if object_id:
                session_key = f'container_referrer_{object_id}'
                request.session[session_key] = back_url
        
        return super().changeform_view(request, object_id, form_url, extra_context)
    
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        """Change the container_number label and make warehouse smaller, format dates"""
        if db_field.name == 'container_number':
            kwargs['label'] = 'Container / Ref Number'
        elif db_field.name == 'warehouse':
            kwargs['widget'] = forms.Select(attrs={'style': 'width: 150px;'})
        elif db_field.name in ['etd', 'eta', 'expiry_date', 'booking_in_date']:
            kwargs['widget'] = admin_widgets.AdminDateWidget(format='%d-%m-%Y')
            kwargs['input_formats'] = ['%d-%m-%Y', '%Y-%m-%d']
        return super().formfield_for_dbfield(db_field, request, **kwargs)
    
    def updated_display(self, obj):
        """Display updated datetime in dd-mm-yyyy HH:MM format"""
        if obj and obj.updated:
            return obj.updated.strftime('%d-%m-%Y %H:%M')
        return "-"
    updated_display.short_description = "Updated Date/Time"
        
    def unit_of_measure_display(self, obj):
        """Display unit of measure from stock_item"""
        if obj and obj.stock_item and obj.stock_item.unit_of_measure:
            return str(obj.stock_item.unit_of_measure)
        return "-"
    unit_of_measure_display.short_description = "Unit of Measure"
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('supplier')
    
    readonly_fields = (
        'display_track_container',
        'updated_display',
        'total_cost_nad',
        'unit_of_measure_display',
        'price_per_unit_display', 
        'total_cost_display',
    )

    list_display = (
        'container_number',
        'supplier', 
        'source',
        'display_eta',
        'price_per_ton_cif',
        'payment_status',
    )
    list_filter = ('payment_status',)
    search_fields = ('container_number', 'supplier__name')

    def display_eta(self, obj):
        return obj.eta.strftime("%d/%m/%Y") if obj.eta else ""
    display_eta.short_description = "ETA"
    
    def display_track_container(self, obj):
        url = obj.get_tracking_url()
        if url:
            return mark_safe(
                '<div style="border:none;padding:0;margin:0;background:none;">'
                '<a href="{0}" target="_blank" style="display:inline-block;padding: 10px 15px; background-color: #417690; color: white; text-decoration: none; border-radius: 4px; border:none !important;">Track Container {1}</a>'
                '</div>'.format(url, obj.container_number)
            )
        return "Set Ship Owner to enable tracking"
    display_track_container.short_description = "Container Tracking"



    fieldsets = (
        ('Stock Classification', {  
            'fields': (
                ('booking_in_date', 'authorized_person'),
                ('item_category', 'sub_category', 'stock_item'),
            )
        }),   
        ('Basic Information', {
            'fields': (
                ('supplier', 'container_number', 'expiry_date'),
                ('status', 'display_track_container', 'updated_display'),
            )
        }),
        ('Dates & Location', {
            'fields': (
                ('etd', 'eta'),  
                ('current_location', 'next_location'), 
            )
        }),
        ('Shipping', {
            'fields': (
                ('vessel', 'booking', 'ship_owner'),
            )
        }),
        ('Packaging Configuration', {
            'classes': ('collapse',), 
            'fields': (
                ('unit_of_measure_display', 'warehouse'),  
                ('kg_per_box', 'total_boxes'),
                ('gross_weight', 'net_weight'),
                ('total_weight_container'),
            )
        }),
        ('Payment', {
            'fields': ('payment_terms', 'payment_status')
        }),
        ('Documentation', {
            'fields': (
                ('permit_number', 'permit_doc'),
                ('invoice', 'invoice_doc'),
                ('po_number', 'po_doc')
            )
        }),
        ('Deposit', {
            'fields': (
                ('deposit_amount', 'deposit_currency_from', 'deposit_currency_to', 'deposit_exchange_rate'),
            )
        }),
        ('Final Payment', {
            'fields': (
                ('final_amount', 'final_currency_from', 'final_currency_to', 'final_exchange_rate'),
            )
        }),
        ('Transport', {
            'fields': (
                ('transport_cost', 'transport_currency_from', 'transport_currency_to', 'transport_exchange_rate', 'transport_doc'),
            )
        }),
        ('Commission', {
            'fields': (
                ('commission', 'commission_currency_from', 'commission_currency_to', 'commission_exchange_rate', 'commission_doc'),
            )
        }),
        ('Duty', {
            'fields': (
                ('duty', 'duty_currency', 'duty_doc'),
            )
        }),
        ('Clearing', {
            'fields': (
                ('clearing', 'clearing_currency', 'clearing_doc'),
            )
        }),
        ('Cost', {
            'fields': (
                ('price_per_unit_display', 'total_cost_nad'),
            )
        }),
        ('Notes', {
            'fields': ('comments',)
        }),
    )
    
    def get_model_perms(self, request):
        """Hide from admin index/dashboard"""
        return {}

    from django.shortcuts import redirect

    def response_add(self, request, obj, post_url_continue=None):
        # Check if user clicked "Save and continue editing"
        if '_continue' in request.POST:
            # Use default behavior (stay on edit page)
            return super().response_add(request, obj, post_url_continue)
        
        # Priority 1: Check for 'next' parameter
        next_url = request.GET.get('next') or request.POST.get('next')
        if next_url:
            return redirect(next_url)
        
        # Priority 2: Check for back_url parameter
        back_url = request.GET.get('back_url', '') or request.POST.get('back_url', '')
        if back_url:
            return redirect(back_url)
        
        # Priority 3: Check session for stored referrer
        if obj.pk:
            session_key = f'container_referrer_{obj.pk}'
            stored_referrer = request.session.get(session_key, '')
            if stored_referrer:
                return redirect(stored_referrer)
        
        # Default: redirect to stock transactions changelist
        return redirect('admin:inventory_stocktransaction_changelist')

    def response_change(self, request, obj):
        # Check if user clicked "Save and continue editing"
        if '_continue' in request.POST:
            # Use default behavior (stay on edit page)
            return super().response_change(request, obj)
        
        # Priority 1: Check for 'next' parameter
        next_url = request.GET.get('next') or request.POST.get('next')
        if next_url:
            return redirect(next_url)
        
        # Priority 2: Check for back_url parameter
        back_url = request.GET.get('back_url', '') or request.POST.get('back_url', '')
        if back_url:
            return redirect(back_url)
        
        # Priority 3: Check session for stored referrer
        if obj.pk:
            session_key = f'container_referrer_{obj.pk}'
            stored_referrer = request.session.get(session_key, '')
            if stored_referrer:
                return redirect(stored_referrer)
        
        # Default: redirect to stock transactions changelist
        return redirect('admin:inventory_stocktransaction_changelist')
    
    class Media:
        js = (
            'js/booking_live_calc.js',
            'js/unit_autofill_stocktransaction.js',
            'js/container_packaging_labels.js',
        )

        
admin.site.register(Container, ContainerAdmin)
        
@admin.register(UnitOfMeasure)
class UnitOfMeasureAdmin(SiteAwareModelAdmin, admin.ModelAdmin):
    search_fields = ['name', 'abbreviation']
    def get_model_perms(self, request):
        return {}

class StockSubCategoryInline(admin.TabularInline):
    model = StockSubCategory
    extra = 1

@admin.register(StockSubCategory)
class StockSubCategoryAdmin(SiteAwareModelAdmin, admin.ModelAdmin):
    list_display = ('name', 'category')
    search_fields = ('name', 'category__name')
    list_filter = ('category',)
    
    fieldsets = (
        ('Sub Category Information', {
            'fields': ('category', 'name')
        }),
    )
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter category dropdown to show only categories for current site"""
        if db_field.name == "category":
            current_site = getattr(request, 'current_site', None)
            if current_site:
                # Site admin: show only categories for this site
                kwargs["queryset"] = StockCategory.objects.filter(site=current_site)
            else:
                # HQ admin: show only HQ categories (site=NULL)
                kwargs["queryset"] = StockCategory.objects.filter(site__isnull=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    def get_exclude(self, request, obj=None):
        """Exclude site field - it's auto-assigned by SiteAwareModelAdmin"""
        exclude = list(super().get_exclude(request, obj) or [])
        if 'site' not in exclude:
            exclude.append('site')
        return exclude
    
    def get_model_perms(self, request):
        return {}

@admin.register(StockItem)
class StockItemAdmin(SiteAwareModelAdmin, ArchivableAdmin):
    list_display = [
        'name', 
        'category', 
        'sub_category', 
        'unit_of_measure',
        'reorder_level',
        'standard_cost_excl_transport_display',
        'standard_cost_incl_transport_display',
    ]
    search_fields = ['name', 'category__name', 'sub_category__name']
    list_filter = ['category', 'sub_category']

    autocomplete_fields = ['category', 'unit_of_measure']

    fieldsets = (
        ('Basic Information', {
            'fields': (
                'category',
                'sub_category',
                'name',
                'unit_of_measure',
            )
        }),
        ('Stock Levels', {
            'fields': ('reorder_level',)
        }),
        ('Standard Cost of Stock Item', {
            'fields': (
                ('standard_cost_excl_transport', 'standard_cost_excl_transport_currency'),
                ('standard_cost_incl_transport', 'standard_cost_incl_transport_currency'),
            )
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
    )
    
    def get_fieldsets(self, request, obj=None):
        """Change fieldset title based on add/edit"""
        fieldsets = super().get_fieldsets(request, obj)
        # Convert tuple to list to allow modification
        fieldsets_list = list(fieldsets)
        
        # First fieldset is (name, config_dict)
        if fieldsets_list:
            first_fieldset = list(fieldsets_list[0])
            if obj is None:
                # Add view: "Add Stock Item"
                first_fieldset[0] = 'Add Stock Item'
            else:
                # Edit view: "Edit Stock Item"
                first_fieldset[0] = 'Edit Stock Item'
            fieldsets_list[0] = tuple(first_fieldset)
        
        return tuple(fieldsets_list)
    
    def add_view(self, request, form_url='', extra_context=None):
        """Override add view to set page title"""
        extra_context = extra_context or {}
        extra_context['title'] = 'Add stock item'
        return super().add_view(request, form_url, extra_context)
    
    def change_view(self, request, object_id, form_url='', extra_context=None):
        """Override change view to set page title"""
        extra_context = extra_context or {}
        extra_context['title'] = 'View stock item'
        return super().change_view(request, object_id, form_url, extra_context)
    
    def get_form(self, request, obj=None, **kwargs):
        """Override form to filter category choices by site"""
        form = super().get_form(request, obj, **kwargs)
        
        # Filter category dropdown to current site only (no global sharing)
        if 'category' in form.base_fields:
            current_site = getattr(request, 'current_site', None)
            if current_site:
                # Site admin: show ONLY categories for this site
                form.base_fields['category'].queryset = StockCategory.objects.filter(site_id=current_site.id)
            else:
                # HQ context - show all categories
                form.base_fields['category'].queryset = StockCategory.objects.all()
        
        return form
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter unit_of_measure by current site"""
        current_site = getattr(request, 'current_site', None)
        
        if db_field.name == "unit_of_measure":
            if current_site:
                # Site admin: show ONLY units for this site
                kwargs["queryset"] = UnitOfMeasure.objects.filter(site=current_site)
            else:
                # HQ context: show all units
                kwargs["queryset"] = UnitOfMeasure.objects.all()
        
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        """Reduce field sizes for category, name, unit_of_measure"""
        if db_field.name == 'category':
            kwargs['widget'] = forms.Select(attrs={'style': 'width: 200px;'})
        elif db_field.name == 'name':
            kwargs['widget'] = forms.TextInput(attrs={'style': 'width: 300px;'})
        elif db_field.name == 'unit_of_measure':
            kwargs['widget'] = forms.Select(attrs={'style': 'width: 150px;'})
        return super().formfield_for_dbfield(db_field, request, **kwargs)
    
    def standard_cost_excl_transport_display(self, obj):
        """Display price excl transport with currency"""
        if obj.standard_cost_excl_transport:
            currency_symbol = 'R' if obj.standard_cost_excl_transport_currency == 'R' else 'N$'
            return f"{currency_symbol} {float(obj.standard_cost_excl_transport):,.2f}"
        return "-"
    standard_cost_excl_transport_display.short_description = "Price Excl Transport"
    
    def standard_cost_incl_transport_display(self, obj):
        """Display price incl transport with currency"""
        if obj.standard_cost_incl_transport:
            currency_symbol = 'R' if obj.standard_cost_incl_transport_currency == 'R' else 'N$'
            return f"{currency_symbol} {float(obj.standard_cost_incl_transport):,.2f}"
        return "-"
    standard_cost_incl_transport_display.short_description = "Price Incl Transport"

    class Media:
        js = ('js/stockitem_icons.js',)

@admin.register(Amendment)
class AmendmentAdmin(admin.ModelAdmin):
    # Form with validation for amendment_type='OUT'
    class AmendmentAdminForm(forms.ModelForm):
        class Meta:
            model = Amendment
            fields = '__all__'

        def clean(self):
            cleaned = super().clean()
            amendment_type = cleaned.get('amendment_type') or getattr(self.instance, 'amendment_type', None)
            batch_ref = cleaned.get('batch_ref') or getattr(self.instance, 'batch_ref', None)
            quantity = cleaned.get('quantity')

            if amendment_type == 'OUT' and batch_ref and quantity:
                from decimal import Decimal
                from django.db.models import Sum
                from .models import Container, StockTransaction as STx, Amendment as Amnd

                total_in = Decimal('0')

                # 1. Add Container IN
                container = Container.objects.filter(container_number=batch_ref).first()
                if container and container.total_weight_container:
                    total_in += container.total_weight_container

                # 2. Add StockTransaction IN
                tx_in = STx.objects.filter(batch_ref=batch_ref, transaction_type='IN').aggregate(total=Sum('quantity'))['total'] or Decimal('0')
                total_in += tx_in

                # 3. Add Amendment IN
                amendments_in = Amnd.objects.filter(batch_ref=batch_ref, amendment_type='IN').aggregate(total=Sum('quantity'))['total'] or Decimal('0')
                total_in += amendments_in

                total_out = Decimal('0')

                # 4. Add StockTransaction OUT
                tx_out = STx.objects.filter(batch_ref=batch_ref, transaction_type='OUT').aggregate(total=Sum('quantity'))['total'] or Decimal('0')
                total_out += tx_out

                # 5. Add Amendment OUT (excluding current amendment if editing)
                amendments_out_qs = Amnd.objects.filter(batch_ref=batch_ref, amendment_type='OUT')
                if self.instance and self.instance.pk:
                    amendments_out_qs = amendments_out_qs.exclude(pk=self.instance.pk)
                amendments_out = amendments_out_qs.aggregate(total=Sum('quantity'))['total'] or Decimal('0')
                total_out += amendments_out

                # 6. Add Production Usage
                try:
                    from inventory.models import PackagingBalance, RecipeStockItemBalance
                    
                    stock_item = None
                    if container and container.stock_item:
                        stock_item = container.stock_item
                    else:
                        tx = STx.objects.filter(batch_ref=batch_ref).first()
                        if tx and tx.stock_item:
                            stock_item = tx.stock_item
                    
                    if stock_item:
                        prod_usage = PackagingBalance.objects.filter(stock_item=stock_item).aggregate(total=Sum('quantity_used'))['total'] or Decimal('0')
                        total_out += prod_usage
                        
                        recipe_usage = RecipeStockItemBalance.objects.filter(stock_item=stock_item).aggregate(total=Sum('quantity_used'))['total'] or Decimal('0')
                        total_out += recipe_usage
                except Exception:
                    pass

                available = total_in - total_out
                if Decimal(str(quantity)) > available:
                    raise forms.ValidationError(
                        (
                            f"AMENDMENT QUANTITY EXCEEDS AVAILABLE STOCK. "
                            f"Amendment Qty: {Decimal(str(quantity)):.2f}. "
                            f"Available Stock: {available:.2f}. "
                            f"Total IN: {total_in:.2f}. Total OUT (incl. Production): {total_out:.2f}. "
                            f"Please reduce the amendment quantity."
                        )
                    )

            return cleaned

    form = AmendmentAdminForm
    list_display = ['date','amendment_type', 'quantity', 'reason', 'person', 'batch_ref']
    change_form_template = "admin/inventory/amendment/change_form.html"
    
    fieldsets = (
        ('Stock Information', {
            'fields': (
                ('stock_item_display', 'date_display'),  
                ('batch_ref',),  # ← ACTUAL FIELD, not display method
                ('unit_of_measure_display',),
            )
        }),
        ('Amendment Details', {
            'fields': (
                ('amendment_type',),
                ('quantity',),
                ('reason',),
                ('person',),
            )
        }),
    )
    list_filter = ['amendment_type', 'person', 'date', 'batch_ref']
    search_fields = ['reason', 'person', 'batch_ref']
    readonly_fields = ['stock_item_display', 'unit_of_measure_display', 'date_display']
    
    def date_display(self, obj):
        """Display date in dd-mm-yyyy format"""
        if obj and obj.date:
            return obj.date.strftime('%d-%m-%Y')
        return "-"
    date_display.short_description = "Date"

    def get_readonly_fields(self, request, obj=None):
        """Make batch_ref read-only only when EDITING (obj exists)"""
        readonly = list(self.readonly_fields)
        if obj:  # Editing existing amendment
            readonly.append('batch_ref')
        return readonly
    
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        """No need for date formatting since date_display handles readonly display"""
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    def get_batch_ref_from_request(self):
        if hasattr(self, 'current_request') and self.current_request:
            return self.current_request.GET.get('batch_ref', '')
        return ''

    def stock_item_display(self, obj):
        if obj and obj.pk and obj.stock_item:
            return str(obj.stock_item)
        
        batch_ref = self.get_batch_ref_from_request()
        if batch_ref:
            from .models import StockTransaction
            tx = StockTransaction.objects.filter(batch_ref=batch_ref).order_by('pk').first()
            if tx and tx.stock_item:
                return str(tx.stock_item)
            
            # ← ADD THIS: Try Container if StockTransaction not found
            from .models import Container
            container = Container.objects.filter(container_number=batch_ref).first()
            if container and container.stock_item:
                return str(container.stock_item)
        
        if obj and obj.batch_ref:
            from .models import StockTransaction
            tx = StockTransaction.objects.filter(batch_ref=obj.batch_ref).order_by('pk').first()
            if tx and tx.stock_item:
                return str(tx.stock_item)
        
        return "-"
    stock_item_display.short_description = "Stock Item"

    def unit_of_measure_display(self, obj):
        if obj and obj.pk and obj.stock_item and obj.stock_item.unit_of_measure:
            return str(obj.stock_item.unit_of_measure)
        
        batch_ref = self.get_batch_ref_from_request()
        if not batch_ref and obj:
            batch_ref = obj.batch_ref
        
        if batch_ref:
            from .models import StockTransaction
            tx = StockTransaction.objects.filter(batch_ref=batch_ref).order_by('pk').first()
            if tx and tx.stock_item and tx.stock_item.unit_of_measure:
                return str(tx.stock_item.unit_of_measure)
            
            # ← ADD THIS: Try Container if StockTransaction not found
            from .models import Container
            container = Container.objects.filter(container_number=batch_ref).first()
            if container and container.stock_item and container.stock_item.unit_of_measure:
                return str(container.stock_item.unit_of_measure)
        
        return "-"
    unit_of_measure_display.short_description = "Unit of Measure"

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        """Override to add back link to parent StockTransaction"""
        extra_context = extra_context or {}
        
        # Priority 1: Check for 'next' parameter
        back_url = request.GET.get('next', '')
        if not back_url:
            # Priority 2: Check for back_url parameter
            back_url = request.GET.get('back_url', '')
        
        if back_url:
            extra_context['back_url'] = back_url
            session_key = f'amendment_referrer_{object_id}'
            request.session[session_key] = back_url
        else:
            # Priority 3: Get the parent transaction if no back_url
            if object_id:
                from .models import Amendment
                try:
                    amendment = Amendment.objects.get(pk=object_id)
                    if amendment.batch_ref:
                        from .models import StockTransaction
                        tx = StockTransaction.objects.filter(batch_ref=amendment.batch_ref).order_by('pk').first()
                        if tx:
                            extra_context['back_url'] = reverse('admin:inventory_stocktransaction_change', args=[tx.pk])
                except:
                    pass
        
        return super().changeform_view(request, object_id, form_url, extra_context)

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        self.current_request = request
        return super().render_change_form(request, context, add, change, form_url, obj)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        batch_ref = request.GET.get('batch_ref')
        
        if obj is None and batch_ref:
            if 'batch_ref' in form.base_fields:
                form.base_fields['batch_ref'].initial = batch_ref
                form.base_fields['batch_ref'].disabled = True 
        
        return form

    def has_module_permission(self, request):
        return False
    
    def save_model(self, request, obj, form, change):
        """Set stock_item from container if not already set"""
        if not obj.stock_item and obj.batch_ref:
            # Try to find container with this batch_ref
            from inventory.models import Container
            container = Container.objects.filter(container_number=obj.batch_ref).first()
            if container and container.stock_item:
                obj.stock_item = container.stock_item
        
        super().save_model(request, obj, form, change)

    def response_add(self, request, obj, post_url_continue=None):
        # Check if user clicked "Save and continue editing"
        if '_continue' in request.POST:
            return super().response_add(request, obj, post_url_continue)
        
        # Priority 1: Check for 'next' parameter
        next_url = request.GET.get('next') or request.POST.get('next')
        if next_url:
            return redirect(next_url)
        
        # Priority 2: Check for back_url parameter
        back_url = request.GET.get('back_url', '') or request.POST.get('back_url', '')
        if back_url:
            return redirect(back_url)
        
        # Priority 3: Get stored referrer from session
        session_key = f'amendment_referrer_{obj.pk}'
        stored_referrer = request.session.get(session_key, '')
        if stored_referrer:
            return redirect(stored_referrer)
        
        # Priority 4: Redirect to stock transaction changelist with category filter
        if obj.batch_ref:
            from .models import StockTransaction, Container
            # Try to get category from StockTransaction
            tx = StockTransaction.objects.filter(batch_ref=obj.batch_ref).order_by('pk').first()
            if tx and tx.stock_item and tx.stock_item.category:
                return redirect(f'/admin/inventory/stocktransaction/?category={tx.stock_item.category.pk}')
            # Try to get category from Container
            container = Container.objects.filter(container_number=obj.batch_ref).first()
            if container and container.stock_item and container.stock_item.category:
                return redirect(f'/admin/inventory/stocktransaction/?category={container.stock_item.category.pk}')
        return redirect('admin:inventory_stocktransaction_changelist')

    def response_change(self, request, obj):
        # Check if user clicked "Save and continue editing"
        if '_continue' in request.POST:
            return super().response_change(request, obj)
        
        # Priority 1: Check for 'next' parameter
        next_url = request.GET.get('next') or request.POST.get('next')
        if next_url:
            return redirect(next_url)
        
        # Priority 2: Check for back_url parameter
        back_url = request.GET.get('back_url', '') or request.POST.get('back_url', '')
        if back_url:
            return redirect(back_url)
        
        # Priority 3: Get stored referrer from session
        session_key = f'amendment_referrer_{obj.pk}'
        stored_referrer = request.session.get(session_key, '')
        if stored_referrer:
            return redirect(stored_referrer)
        
        # Priority 4: Redirect to stock transaction changelist with category filter
        if obj.batch_ref:
            from .models import StockTransaction, Container
            # Try to get category from StockTransaction
            tx = StockTransaction.objects.filter(batch_ref=obj.batch_ref).order_by('pk').first()
            if tx and tx.stock_item and tx.stock_item.category:
                return redirect(f'/admin/inventory/stocktransaction/?category={tx.stock_item.category.pk}')
            # Try to get category from Container
            container = Container.objects.filter(container_number=obj.batch_ref).first()
            if container and container.stock_item and container.stock_item.category:
                return redirect(f'/admin/inventory/stocktransaction/?category={container.stock_item.category.pk}')
        return redirect('admin:inventory_stocktransaction_changelist')


@admin.register(StockCategory)
class StockCategoryAdmin(SiteAwareModelAdmin, admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

    def has_module_permission(self, request):
        return False


from commercial.models import Supplier
from .models import StockCategory, StockSubCategory, StockTransaction
   
@admin.register(StockTransaction)
class StockTransactionAdmin(SiteAwareModelAdmin, admin.ModelAdmin):
    def add_view(self, request, form_url='', extra_context=None):
        """Override add_view to inject category from query string or batch_ref into POST"""
        category_id = request.GET.get('category')
        transaction_type = request.GET.get('transaction_type', 'IN')
        batch_ref = request.GET.get('batch_ref')
        
        # For OUT bookings without explicit category, try to get from batch_ref
        if not category_id and transaction_type == 'OUT' and batch_ref:
            from .models import Container, StockTransaction
            # Try to get category from container
            container = Container.objects.filter(container_number=batch_ref).first()
            if container and container.stock_item and container.stock_item.category:
                category_id = container.stock_item.category.id
            else:
                # Fallback to stock transaction
                tx = StockTransaction.objects.filter(batch_ref=batch_ref).order_by('pk').first()
                if tx and tx.stock_item and tx.stock_item.category:
                    category_id = tx.stock_item.category.id
        
        # For both GET and POST, inject category
        if category_id:
            if request.method == 'POST' and 'category' not in request.POST:
                # Inject into POST for form processing as STRING (form data must be strings)
                try:
                    request.POST._mutable = True
                    request.POST['category'] = str(category_id)  # Convert to string
                    request.POST._mutable = False
                except Exception as e:
                    print(f"[Category Injection] POST mutation failed: {e}")
            
            # Also store on request as backup
            request._category_id_fallback = category_id
        
        return super().add_view(request, form_url, extra_context)
    
    def get_form(self, request, obj=None, **kwargs):
        """Ensure instance has category before form renders"""
        # If this is a new object (obj is None), check for category from multiple sources
        category_id = None
        
        if obj is None:
            # 1. Check GET params first
            category_id = request.GET.get('category')
            
            # 2. Check POST data (injected by add_view)
            if not category_id and request.method == 'POST':
                category_id = request.POST.get('category')
            
            # 3. Check request fallback (set by add_view)
            if not category_id and hasattr(request, '_category_id_fallback'):
                category_id = request._category_id_fallback
            
            # Create a temporary instance with the category pre-set to avoid RelatedObjectDoesNotExist
            if category_id:
                try:
                    from .models import StockCategory, StockTransaction
                    category = StockCategory.objects.get(id=category_id)
                    # Create instance with category_id set (not category relation, to be safe)
                    obj = StockTransaction()
                    obj.category_id = int(category_id)
                    # Store in request so form knows this was injected
                    request._injected_instance = True
                except (StockCategory.DoesNotExist, ValueError, TypeError):
                    # If we can't find category, just proceed without pre-setting it
                    # The form __init__ will try to handle it
                    pass
        
        # Pass request to form
        kwargs['request'] = request
        return super().get_form(request, obj, **kwargs)
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter foreign key dropdowns by site"""
        current_site = getattr(request, 'current_site', None)
        
        if db_field.name == "supplier":
            from commercial.models import Supplier
            if current_site:
                kwargs["queryset"] = Supplier.objects.filter(site_id=current_site.id)
            else:
                kwargs["queryset"] = Supplier.objects.all()
        elif db_field.name == "warehouse":
            from commercial.models import Warehouse
            if current_site:
                kwargs["queryset"] = Warehouse.objects.filter(site_id=current_site.id)
            else:
                kwargs["queryset"] = Warehouse.objects.all()
        elif db_field.name == "category":
            from .models import StockCategory
            if current_site:
                kwargs["queryset"] = StockCategory.objects.filter(site_id=current_site.id)
            else:
                kwargs["queryset"] = StockCategory.objects.all()
        elif db_field.name == "container":
            from .models import Container
            if current_site:
                kwargs["queryset"] = Container.objects.filter(site_id=current_site.id)
            else:
                kwargs["queryset"] = Container.objects.all()
        elif db_field.name == "batch":
            from manufacturing.models import Batch
            if current_site:
                kwargs["queryset"] = Batch.objects.filter(site_id=current_site.id)
            else:
                kwargs["queryset"] = Batch.objects.all()
        elif db_field.name == "transporter":
            from commercial.models import Transporter
            if current_site:
                kwargs["queryset"] = Transporter.objects.filter(site_id=current_site.id)
            else:
                kwargs["queryset"] = Transporter.objects.all()
        
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    # Use a ModelForm to provide server-side validation that keeps users
    # on the form with a red error line when quantity exceeds available.
    class StockTransactionAdminForm(forms.ModelForm):
        # Create category field explicitly so we control how it's rendered
        category = forms.ModelChoiceField(
            queryset=StockCategory.objects.all(),
            required=False,  # Changed to False - will be validated in clean() method if needed
            label="Item Category"
        )
        
        def __init__(self, *args, **kwargs):
            # Capture request and batch_ref from kwargs so validation can use them
            self.request = kwargs.pop('request', None)
            self.batch_ref = kwargs.pop('batch_ref', None)
            
            # CRITICAL: Ensure instance has category_id BEFORE super().__init__()
            # to prevent RelatedObjectDoesNotExist errors during form initialization
            if 'instance' not in kwargs or kwargs['instance'] is None:
                # For new objects, create instance with category_id pre-set
                category_id = None
                
                # Try to get category from all sources
                if len(args) > 0 and args[0]:
                    # Check POST data first (args[0] is data)
                    category_id = args[0].get('category')
                
                if not category_id and self.request:
                    # Check GET params
                    category_id = self.request.GET.get('category')
                
                if not category_id and self.request:
                    # Check request attributes
                    category_id = getattr(self.request, '_category_id_for_form', None)
                    if not category_id:
                        category_id = getattr(self.request, '_category_id_fallback', None)
                
                # Create instance with category_id set
                if category_id:
                    try:
                        from .models import StockTransaction
                        instance = StockTransaction()
                        instance.category_id = int(category_id)
                        kwargs['instance'] = instance
                    except (ValueError, TypeError):
                        pass
            
            # CRITICAL: Inject category into POST data BEFORE calling super().__init__()
            # This ensures category is available when form fields are initialized
            if len(args) > 0 and args[0]:  # args[0] is the data (POST or None)
                data = args[0]
                if 'category' not in data:  # Only inject if not already present
                    # Try to get category from multiple sources
                    category_id = None
                    
                    # 1. Check request GET params
                    if self.request:
                        category_id = self.request.GET.get('category')
                    
                    # 2. Check request attribute set by get_form()
                    if not category_id and self.request and hasattr(self.request, '_category_id_for_form'):
                        category_id = self.request._category_id_for_form
                    
                    # 3. Check request fallback (set by add_view)
                    if not category_id and self.request and hasattr(self.request, '_category_id_fallback'):
                        category_id = self.request._category_id_fallback
                    
                    # If we found a category, inject it into POST data as string
                    if category_id:
                        if hasattr(data, '_mutable'):
                            # QueryDict (from POST)
                            data._mutable = True
                            data['category'] = str(category_id)
                            data._mutable = False
                        else:
                            # Regular dict - shouldn't happen but handle it
                            if not isinstance(data, dict):
                                data = dict(data)
                            else:
                                data = data.copy()
                            data['category'] = str(category_id)
                            args = (data,) + args[1:]
            
            super().__init__(*args, **kwargs)
            
            # For new objects, ensure category_id is set from form data if not already set
            if self.request and not self.instance.pk:
                # If instance doesn't have category_id yet, try to set it from form data
                if not self.instance.category_id:
                    category_id = self.data.get('category') if self.is_bound else self.request.GET.get('category')
                    if category_id:
                        try:
                            self.instance.category_id = int(category_id)
                            self.fields['category'].initial = category_id
                        except (ValueError, TypeError):
                            pass
            
            # For existing objects being edited, ensure category is populated
            # even if it wasn't in POST data (it may have come from query string injection above)
            elif self.instance.pk and self.instance.category_id:
                # Make sure the category is set on the form
                self.fields['category'].initial = self.instance.category_id
            
            # Filter stock_item queryset by current site
            if 'stock_item' in self.fields and self.request:
                current_site = getattr(self.request, 'current_site', None)
                if current_site:
                    # Site context: show ONLY stock items for this site
                    from .models import StockItem
                    self.fields['stock_item'].queryset = StockItem.objects.filter(site_id=current_site.id)
                else:
                    # HQ context: show all stock items
                    from .models import StockItem
                    self.fields['stock_item'].queryset = StockItem.objects.all()
            
            # Apply DisabledSelect to stock_item if this is an OUT booking
            # This runs on every form instantiation including error re-renders
            is_out_booking = False
            
            if self.instance and self.instance.pk and self.instance.transaction_type == 'OUT':
                is_out_booking = True
            else:
                # Check GET params first, then session (for NEW records)
                transaction_type = None
                if self.request:
                    transaction_type = self.request.GET.get('transaction_type')
                    if not transaction_type:
                        transaction_type = self.request.session.get('transaction_type')
                
                if transaction_type == 'OUT':
                    is_out_booking = True
            
            if is_out_booking and 'stock_item' in self.fields:
                stock_item_pk = None
                
                # Find stock_item from batch_ref
                if self.batch_ref:
                    from .models import Container, StockTransaction
                    container = Container.objects.filter(container_number=self.batch_ref).first()
                    if container and container.stock_item:
                        stock_item_pk = container.stock_item.pk
                    else:
                        tx = StockTransaction.objects.filter(batch_ref=self.batch_ref).order_by('pk').first()
                        if tx and tx.stock_item:
                            stock_item_pk = tx.stock_item.pk
                
                if stock_item_pk:
                    # Set initial value - this works for unbound forms
                    self.fields['stock_item'].initial = stock_item_pk
                    
                    # For bound forms (POST with errors), we need to override data
                    if self.is_bound and not self.data.get('stock_item'):
                        # Create mutable copy of data and set stock_item
                        self.data = self.data.copy()
                        self.data['stock_item'] = str(stock_item_pk)
                
                # Preserve help_text and apply DisabledSelect widget
                stock_item_field = self.fields['stock_item']
                old_help_text = stock_item_field.help_text
                
                self.fields['stock_item'].widget = DisabledSelect(
                    choices=stock_item_field.choices
                )
                self.fields['stock_item'].help_text = old_help_text
                self.fields['stock_item'].required = False

        def full_clean(self):
            """Override to validate the form"""
            super().full_clean()

        def clean(self):
            cleaned_data = super().clean()
            
            transaction_type = cleaned_data.get('transaction_type')
            # For OUT bookings without transaction_type in cleaned_data, check instance or request
            if not transaction_type:
                if self.instance and self.instance.pk:
                    transaction_type = self.instance.transaction_type
                elif self.request:
                    # Check GET first, then session (like get_fieldsets does)
                    transaction_type = self.request.GET.get('transaction_type')
                    if not transaction_type:
                        transaction_type = self.request.session.get('transaction_type')
            
            # Ensure category is available (from form or query string)
            if not cleaned_data.get('category') and self.request:
                category_id = self.request.GET.get('category')
                if category_id:
                    from .models import StockCategory
                    try:
                        cleaned_data['category'] = StockCategory.objects.get(id=category_id)
                    except StockCategory.DoesNotExist:
                        pass  # Will be set by save_model
            
            # For editing existing records, use instance category if not in cleaned_data
            # Use category_id to avoid accessing relation that might not exist
            if not cleaned_data.get('category') and self.instance and self.instance.pk and self.instance.category_id:
                # Use category_id lookup instead of accessing relationship
                from .models import StockCategory
                try:
                    cleaned_data['category'] = StockCategory.objects.get(id=self.instance.category_id)
                except StockCategory.DoesNotExist:
                    pass
            
            # For OUT bookings, get category from stock_item if not already set
            # Note: stock_item is a disabled field, so we need to get it from self.data or initial
            if not cleaned_data.get('category') and transaction_type == 'OUT':
                stock_item_obj = cleaned_data.get('stock_item')
                
                # If stock_item is not in cleaned_data (disabled field), try to get from initial or data
                if not stock_item_obj and self.is_bound:
                    stock_item_id = self.data.get('stock_item')
                    if stock_item_id:
                        from .models import StockItem
                        try:
                            stock_item_obj = StockItem.objects.get(id=stock_item_id)
                        except StockItem.DoesNotExist:
                            pass
                
                if stock_item_obj and stock_item_obj.category:
                    cleaned_data['category'] = stock_item_obj.category
            
            # Category is required for NEW records (except OUT which gets it from stock_item), but not for edits (already set)
            if not cleaned_data.get('category'):
                if not self.instance.pk:
                    # New record - category is required (unless it's OUT which should have gotten it from stock_item)
                    if transaction_type == 'OUT':
                        # For OUT bookings, skip validation error - category should come from save_model fallback
                        pass
                    else:
                        raise forms.ValidationError("Category is required")
            
            transaction_type = cleaned_data.get('transaction_type')
            
            # For OUT bookings without transaction_type in cleaned_data, check instance or request
            if not transaction_type:
                if self.instance and self.instance.pk:
                    transaction_type = self.instance.transaction_type
                elif self.request:
                    # Check GET first, then session (like get_fieldsets does)
                    transaction_type = self.request.GET.get('transaction_type')
                    if not transaction_type:
                        transaction_type = self.request.session.get('transaction_type')

            # Get batch_ref from cleaned_data, then self.batch_ref, then instance
            batch_ref = cleaned_data.get('batch_ref') or self.batch_ref
            if not batch_ref and self.instance and self.instance.pk:
                batch_ref = self.instance.batch_ref

            # Validate: Only ONE Booking In (transaction_type='IN') per batch_ref
            # Also check that no Container exists with this batch_ref (container_number)
            if transaction_type == 'IN' and batch_ref:
                from .models import Container
                
                # Check if a Container already exists with this batch_ref
                if Container.objects.filter(container_number=batch_ref).exists():
                    raise forms.ValidationError(
                        f"An Import Book In (Container) already exists for batch reference '{batch_ref}'. "
                        f"Only one Booking In is allowed per batch."
                    )
                
                # Check if a StockTransaction IN already exists
                existing_in_qs = StockTransaction.objects.filter(
                    batch_ref=batch_ref, transaction_type='IN'
                )
                # Exclude current instance if editing
                if self.instance.pk:
                    existing_in_qs = existing_in_qs.exclude(pk=self.instance.pk)
                
                if existing_in_qs.exists():
                    raise forms.ValidationError(
                        f"A Booking In transaction already exists for batch reference '{batch_ref}'. "
                        f"Only one Booking In is allowed per batch."
                    )

            # Only validate quantity for OUT bookings - but SKIP if we're EDITING an existing record
            if transaction_type != 'OUT' or self.instance.pk:
                # Skip validation when editing existing OUT records (they were already valid)
                return cleaned_data

            # Get the quantity being booked out for validation
            qty = cleaned_data.get('quantity')

            if not batch_ref or not qty:
                return cleaned_data

            from decimal import Decimal
            from django.db.models import Sum
            from .models import Amendment, Container

            total_in = Decimal('0')

            # Get IN from container
            container = Container.objects.filter(container_number=batch_ref).first()
            if container and container.total_weight_container:
                total_in += container.total_weight_container

            # Get IN from stock transactions
            tx_in = StockTransaction.objects.filter(
                batch_ref=batch_ref, transaction_type='IN'
            ).aggregate(total=Sum('quantity'))['total'] or Decimal('0')
            total_in += tx_in

            # Amendment IN (Booking Back In) - this REDUCES total OUT, not adds to IN
            amend_in = Amendment.objects.filter(
                batch_ref=batch_ref, amendment_type='IN'
            ).aggregate(total=Sum('quantity'))['total'] or Decimal('0')

            total_out = Decimal('0')

            # Get OUT from stock transactions (exclude current if editing)
            tx_out_qs = StockTransaction.objects.filter(
                batch_ref=batch_ref, transaction_type='OUT'
            )
            if self.instance.pk:
                tx_out_qs = tx_out_qs.exclude(pk=self.instance.pk)

            tx_out = tx_out_qs.aggregate(total=Sum('quantity'))['total'] or Decimal('0')
            total_out += tx_out

            # Amendment OUT (Extra Use) - adds to total OUT
            amend_out = Amendment.objects.filter(
                batch_ref=batch_ref, amendment_type='OUT'
            ).aggregate(total=Sum('quantity'))['total'] or Decimal('0')
            total_out += amend_out

            # Amendment IN (Booking Back In) - REDUCES total OUT
            total_out -= amend_in

            available = total_in - total_out

            if Decimal(str(qty)) > available:
                raise forms.ValidationError(
                    f"BOOKING OUT EXCEEDS AVAILABLE STOCK. "
                    f"Booking Out Qty: {Decimal(str(qty)):.2f}. "
                    f"Available Stock: {available:.2f}. "
                    f"Total IN: {total_in:.2f}. Total OUT: {total_out:.2f}. "
                    f"Please reduce the booking out quantity."
                )

            return cleaned_data

        class Meta:
            model = StockTransaction
            fields = '__all__'

    form = StockTransactionAdminForm
    actions = ['archive_batch_group']
    change_form_template = "admin/inventory/stocktransaction/change_form.html"
    # ❌ REMOVED list_filter - Django's filtering was causing redirects and infinite loops
    # The JavaScript handles all filtering client-side, so we don't need Django filtering
    
    def archive_batch_group(self, request, queryset):
        """Archive all transactions in the selected batch groups"""
        batch_refs = queryset.values_list('batch_ref', flat=True).distinct()
        
        # Archive ALL transactions with these batch_refs
        updated = StockTransaction.objects.filter(
            batch_ref__in=batch_refs
        ).update(is_archived=True)
        
        self.message_user(request, f"{updated} transactions archived (complete batch groups)")
    
    archive_batch_group.short_description = "Archive selected batch groups"
    search_fields = ['stock_item__name', 'batch_ref', 'supplier__name']
    
    readonly_fields = [
        'price_excl_transport_per', 'price_incl_transport_per',
        'cost_per_unit', 'linked_batch_qty_display', 'price_per_unit', 'unit_display', 'unit_of_measure_display', 'price_per_unit_display', 
    'total_cost_display', 
    ]  
    autocomplete_fields = ['warehouse']
    
    def get_readonly_fields(self, request, obj=None):
        readonly = list(self.readonly_fields)
        readonly.append('transaction_type')
        if obj and obj.transaction_type == 'OUT':
            readonly.extend(['stock_item', 'batch_ref'])
        return readonly

    def stock_item_category(self, obj):
        if obj.stock_item and obj.stock_item.category:
            return obj.stock_item.category
        return "-"
    stock_item_category.short_description = "Category"

    def get_amendment_qty(self, obj):
        total_amend_qty = Amendment.objects.filter(batch_ref=obj.batch_ref).aggregate(
            sum=Sum('quantity')
        )['sum'] or 0
    
        if total_amend_qty > 0:
            first_amendment = Amendment.objects.filter(batch_ref=obj.batch_ref).first()
            if first_amendment:
                # Include back_url parameter so amendment knows where to return to
                from django.utils.http import urlencode
                params = urlencode({'back_url': f"/admin/inventory/stocktransaction/{obj.pk}/change/"})
                url = f"{reverse('admin:inventory_amendment_change', args=[first_amendment.pk])}?{params}"
                return format_html(
                    '<a href="{}"><strong>{}</strong></a>',
                    url,
                    total_amend_qty
                )
        return "0.00"
    get_amendment_qty.short_description = "Amendment Qty"

    def get_amendment_qty_display(self, obj):
        first_transaction = StockTransaction.objects.filter(batch_ref=obj.batch_ref).order_by('pk').first()
    
        if first_transaction.pk != obj.pk:
            return "-"
    
        total_amend_qty = Amendment.objects.filter(batch_ref=obj.batch_ref).aggregate(
            sum=Sum('quantity')
        )['sum'] or 0
    
        if total_amend_qty > 0:
            first_amendment = Amendment.objects.filter(batch_ref=obj.batch_ref).first()
            if first_amendment:
                # Include back_url parameter so amendment knows where to return to
                from django.utils.http import urlencode
                params = urlencode({'back_url': f"/admin/inventory/stocktransaction/{obj.pk}/change/"})
                url = f"{reverse('admin:inventory_amendment_change', args=[first_amendment.pk])}?{params}"
                return format_html(
                    '<a href="{}"><strong>{}</strong></a>',
                    url,
                    total_amend_qty
                )
        return "0.00"
    get_amendment_qty_display.short_description = "Amendment Qty"

    def unit_display(self, obj):
        if obj and obj.stock_item and obj.stock_item.unit_of_measure:
            return str(obj.stock_item.unit_of_measure)
        return "-"

    unit_display.short_description = "Unit"
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'archive-batch/',
                self.admin_site.admin_view(self.archive_batch_view),
                name='stocktransaction_archive_batch',
            ),
        ]
        return custom_urls + urls
        
    def archive_batch_view(self, request):
        """Archive or restore all transactions in a batch group"""
        from django.http import JsonResponse
        
        batch_ref = request.GET.get('batch_ref')
        action = request.GET.get('action')
        
        if not batch_ref or not action:
            return JsonResponse({'success': False, 'error': 'Missing parameters'})
        
        # Update all transactions with this batch_ref
        is_archived = (action == 'archive')
        updated = StockTransaction.objects.filter(batch_ref=batch_ref).update(is_archived=is_archived)
        
        return JsonResponse({'success': True, 'updated': updated})

    def add_view(self, request, form_url='', extra_context=None):
        """Override add_view to allow custom transaction types"""
        extra_context = extra_context or {}
        transaction_type = request.GET.get('transaction_type', 'IN')
        
        # Store transaction type in session so get_fieldsets can access it
        request.session['transaction_type'] = transaction_type
        extra_context['transaction_type'] = transaction_type
        
        return super().add_view(request, form_url, extra_context)

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        """Override to add back link to parent filtered view"""
        extra_context = extra_context or {}
        
        # Priority 1: Check for 'next' parameter (already being passed by the system)
        back_url = request.GET.get('next', '')
        if not back_url:
            # Priority 2: Check for back_url in GET parameters
            back_url = request.GET.get('back_url', '')
        
        if back_url:
            extra_context['back_url'] = back_url
            session_key = f'stocktransaction_referrer_{object_id}'
            request.session[session_key] = back_url
        
        return super().changeform_view(request, object_id, form_url, extra_context)
 
    def get_fieldsets(self, request, obj=None):
        # Try to get from GET params first, then session
        transaction_type = request.GET.get('transaction_type')
        if not transaction_type:
            transaction_type = request.session.get('transaction_type', 'IN')

        if transaction_type == 'OUT':
            # Booking Out form
            return (
                ('Booking Out Sheet', {
                    'fields': (
                        ('stock_item', 'transaction_date'),          
                        ('batch_ref',),            
                        ('quantity', 'unit_of_measure_display'),
                        ('authorized_person',),
                    ),
                }),
            )
        elif transaction_type == 'CONTAINER_IN':
            # Container Booking In form (READ-ONLY, pulls from Container)
            return (
                ('Booking In Sheet', {
                    'fields': (
                        ('transaction_date', 'authorized_person'),  
                        ('category', 'sub_category', 'stock_item'),   
                        ('supplier', 'batch_ref', 'expiry_date'),       
                        ('status', 'transporter', 'delivery_date'),                                 
                    ),
                }),
                ('Costing', {
                    'fields': (
                        ('currency',),
                        ('total_invoice_amount_excl', 'transport_cost'),
                        ('price_per_unit_display', 'total_cost_display'),
                        ('invoice_document', 'transporter_document'),
                    ),
                }),
                ('Notes', {
                    'fields': ('usage_notes',)
                }),
            )
        else:
            # Regular Booking In form
            return (
                ('Booking In Sheet', {
                    'fields': (
                        ('transaction_date', 'authorized_person'),  
                        ('category', 'sub_category', 'stock_item'),   
                        ('supplier', 'batch_ref', 'expiry_date'),       
                        ('status', 'transporter', 'delivery_date'),                                 
                    ),
                }),
                ('Packaging Configuration', {
                    'classes': ('collapse',),  
                    'fields': (
                        ('unit_of_measure_display', 'warehouse'),  
                        ('kg_per_box', 'total_boxes'),
                        ('gross_weight', 'net_weight'),
                        ('booking_in_total_qty',),
                    ),
                }),
                ('Costing', {
                    'fields': (
                        ('currency',),
                        ('total_invoice_amount_excl', 'transport_cost'),
                        ('price_per_unit_display', 'total_cost_display'),
                        ('invoice_document', 'transporter_document'),
                    ),
                }),
                ('Notes', {
                    'fields': ('usage_notes',)
                }),
            )

    def has_add_permission(self, request):
        # Allow add if transaction_type is in GET, or if user has add permission via session
        # Default to allowing 'IN' transactions if no type specified
        transaction_type = request.GET.get('transaction_type') or request.session.get('transaction_type', 'IN')
        return transaction_type in ('IN', 'OUT')
  
    def transaction_type_display(self, obj):
        url = reverse('admin:inventory_stocktransaction_change', args=[obj.pk])
        trans_type = obj.get_transaction_type_display()
        return format_html(
            '<a href="{}" style="color: #417690; text-decoration: none; font-weight: bold;">{}</a>',
            url, 
            trans_type
        )
    transaction_type_display.short_description = "Transaction type"

    list_display = [
        'transaction_type_display',
        'stock_item',
        'quantity',
        'unit_of_measure_display',
        'available_stock',
        'get_amendment_type',
        'get_amendment_reason', 
        'get_amendment_qty_display', 
        'transaction_date',
        'supplier',
        'batch_ref',
    ]

    def get_amendment_type(self, obj):
        amendments = Amendment.objects.filter(batch_ref=obj.batch_ref)
        return ", ".join(a.get_amendment_type_display() for a in amendments) if amendments.exists() else "-"
    get_amendment_type.short_description = "Amendment type"

    def get_amendment_reason(self, obj):
        amendments = Amendment.objects.filter(batch_ref=obj.batch_ref)
        return ", ".join(a.reason for a in amendments) if amendments.exists() else "-"
    get_amendment_reason.short_description = "Amendment reason"
  
    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        extra_context = extra_context or {}
    
        transaction_type = request.GET.get('transaction_type')
    
        if request.method == 'GET' and object_id is None and transaction_type in ['IN', 'OUT']:
            extra_context['transaction_type'] = transaction_type
    
        return super().changeform_view(request, object_id, form_url, extra_context)
        
    def available_stock(self, obj):
        # Safely get category name without triggering RelatedObjectDoesNotExist
        category = ""
        if obj.stock_item and obj.stock_item.category_id:
            try:
                category = getattr(obj.stock_item.category, "name", "").lower()
            except (AttributeError, Exception):
                category = ""
        if category == "liver":
            total_in = Container.objects.filter(supplier__category__name__iexact='Liver').aggregate(
            sum=Sum('total_weight_container'))['sum'] or 0

            total_out = StockTransaction.objects.filter(
                stock_item=obj.stock_item, transaction_type='OUT'
            ).aggregate(sum=Sum('quantity'))['sum'] or 0

            liver_waste = BatchProductInventoryUsed.objects.filter(
                stock_item=obj.stock_item
            ).aggregate(sum=Sum('waste_qty'))['sum'] or 0

            available = total_in - total_out - liver_waste
            return "{:.2f}".format(available)

        qs = StockTransaction.objects.filter(stock_item=obj.stock_item)
        stock_in = qs.filter(transaction_type='IN').aggregate(sum=Sum('quantity'))['sum'] or 0
        stock_out = qs.filter(transaction_type='OUT').aggregate(sum=Sum('quantity'))['sum'] or 0
        total = stock_in - stock_out
        return "{:.2f}".format(total)

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        """Make warehouse field smaller inline and format dates"""
        if db_field.name == 'warehouse':
            kwargs['widget'] = forms.Select(attrs={'style': 'width: 150px;'})
        elif db_field.name in ['delivery_date', 'expiry_date', 'transaction_date']:
            kwargs['widget'] = admin_widgets.AdminDateWidget(format='%d-%m-%Y')
            kwargs['input_formats'] = ['%d-%m-%Y', '%Y-%m-%d']
        return super().formfield_for_dbfield(db_field, request, **kwargs)    

    def get_queryset(self, request):
        # Parent class (SiteAwareModelAdmin) handles site filtering
        qs = super().get_queryset(request)
        # Just add ordering
        return qs.order_by('batch_ref', 'pk')

    def get_form(self, request, obj=None, **kwargs):
        batch_ref = request.GET.get('batch_ref')
        transaction_type = request.GET.get('transaction_type', None)
        
        # Store category info on request so form __init__ can use it
        if obj is None:
            # Try to get category from all sources
            category_id = request.GET.get('category') or request.POST.get('category')
            if not category_id and hasattr(request, '_category_id_fallback'):
                category_id = request._category_id_fallback
            if category_id:
                request._category_id_for_form = category_id
        
        base_form = super().get_form(request, obj, **kwargs)

        # Create wrapper that injects request and batch_ref
        class FormWithContext(base_form):
            def __init__(self, *args, **kw):
                kw['request'] = request
                kw['batch_ref'] = batch_ref
                super().__init__(*args, **kw)

        is_booking_out = False

        if obj and hasattr(obj, "transaction_type") and obj.transaction_type == 'OUT':
            is_booking_out = True
        elif not obj and transaction_type == "OUT":
            is_booking_out = True

        if is_booking_out and batch_ref:
            from .models import StockTransaction, Container
            stock_item_obj = None
            
            # ✅ TRY CONTAINER FIRST (batch_ref = container_number)
            container = Container.objects.filter(container_number=batch_ref).first()
            if container and container.stock_item:
                stock_item_obj = container.stock_item
                # ✅ ALSO SET SUPPLIER FROM CONTAINER
                if container.supplier and 'supplier' in FormWithContext.base_fields:
                    FormWithContext.base_fields['supplier'].initial = container.supplier.pk
            else:
                # FALLBACK TO STOCK TRANSACTION
                tx = StockTransaction.objects.filter(batch_ref=batch_ref).order_by('pk').first()
                if tx and tx.stock_item:
                    stock_item_obj = tx.stock_item

            if stock_item_obj and 'stock_item' in FormWithContext.base_fields:
                FormWithContext.base_fields['stock_item'].initial = stock_item_obj.pk
                self._stock_item_to_save = stock_item_obj
            
            if 'batch_ref' in FormWithContext.base_fields:
                FormWithContext.base_fields['batch_ref'].initial = batch_ref
                FormWithContext.base_fields['batch_ref'].disabled = True

        if is_booking_out and 'transaction_date' in FormWithContext.base_fields:
            FormWithContext.base_fields['transaction_date'].label = 'Booking Out Date'

        # For OUT bookings, add category as a hidden field so it can be auto-populated from batch_ref
        if is_booking_out:
            # Add hidden category field that won't be displayed but will accept POST data
            from django import forms
            from .models import StockCategory
            FormWithContext.base_fields['category'] = forms.ModelChoiceField(
                queryset=StockCategory.objects.all(),
                widget=forms.HiddenInput(),
                required=False
            )

        if obj and obj.supplier_id and 'supplier' in FormWithContext.base_fields:
            FormWithContext.base_fields['supplier'].initial = obj.supplier_id

        return FormWithContext

    def save_model(self, request, obj, form, change):
        if not change and hasattr(self, '_stock_item_to_save'):
            obj.stock_item = self._stock_item_to_save
            # ✅ ONLY set category from stock_item if user didn't explicitly select one
            # (i.e., if category is still None/empty). Don't override user selection.
            if not obj.category_id and self._stock_item_to_save and self._stock_item_to_save.category_id:
                obj.category_id = self._stock_item_to_save.category_id
        
        # Set transaction_type from URL for new records
        if not change:
            transaction_type = request.GET.get('transaction_type', 'IN')
            obj.transaction_type = transaction_type
        
        # For OUT bookings, ensure category is set from stock_item if still missing
        if not obj.category_id and obj.stock_item and obj.stock_item.category_id:
            obj.category_id = obj.stock_item.category_id
        
        # Fallback: For OUT bookings, try to get category from batch_ref if still missing
        if not obj.category_id and obj.transaction_type == 'OUT' and obj.batch_ref:
            from .models import Container
            container = Container.objects.filter(container_number=obj.batch_ref).first()
            if container and container.stock_item and container.stock_item.category_id:
                obj.category_id = container.stock_item.category_id
            else:
                tx = StockTransaction.objects.filter(batch_ref=obj.batch_ref).order_by('pk').first()
                if tx and tx.stock_item and tx.stock_item.category_id:
                    obj.category_id = tx.stock_item.category_id
        
        # ✅ ALWAYS CALCULATE AND UPDATE QUANTITY FROM PACKAGING CONFIG
        # This runs on BOTH create AND edit
        if obj.kg_per_box and obj.total_boxes:
            # Calculate from packaging config
            obj.quantity = Decimal(str(obj.kg_per_box)) * Decimal(str(obj.total_boxes))
        elif (not change) and (not obj.quantity or obj.quantity == 0):
            # Only fallback to net_weight on NEW records if no packaging config
            obj.quantity = obj.net_weight or Decimal('0')
        
        super().save_model(request, obj, form, change)

    def changelist_view(self, request, extra_context=None):
        """Render stock transactions with batch tracker and category filtering"""
        extra_context = extra_context or {}
        # Hide the default "+ Add" button - users must use "Local Book In" or "Import Book In" buttons
        extra_context['has_add_permission'] = False
        
        response = super().changelist_view(request, extra_context)
        
        # If Django returned a redirect (trying to clean up params), just let it through
        # The JavaScript will re-load with whatever URL the browser ends up at
        if response.status_code == 302:
            return response
        
        try:
            # ✅ FIX: Default to active, explicit for archived
            is_archived = request.GET.get('is_archived', '0')  # Default '0' not None
            
            # ✅ SITE FILTERING: Get current site from request
            current_site = getattr(request, 'current_site', None)
            
            if is_archived == '1':
                base_filter = {'is_archived': True}
            else:
                base_filter = {'is_archived': False}  # Explicit False
            
            # ✅ ADD SITE FILTER: Only show data for current site (or all for HQ)
            if current_site:
                base_filter['site'] = current_site
            
            batches = {}

            # ADD CONTAINERS FIRST
            container_qs = Container.objects.select_related(
                'item_category',
                'sub_category', 
                'stock_item',
                'warehouse',
                'supplier'
            )
            # ✅ FILTER CONTAINERS BY SITE
            if current_site:
                container_qs = container_qs.filter(site=current_site)
            
            for container in container_qs:
                batch_ref = container.container_number  # Use container number as batch_ref
                item_name = str(container.stock_item) if container.stock_item else 'Unknown'

                if batch_ref not in batches:
                    batches[batch_ref] = {}
                if item_name not in batches[batch_ref]:
                    batches[batch_ref][item_name] = []

                cat_id = container.item_category.id if container.item_category else None
                subcat_id = container.sub_category.id if container.sub_category else None
                
                # GET booking_in_date FOR THE DATE COLUMN; BLANK IF NOT SET
                transaction_date = container.booking_in_date.isoformat() if container.booking_in_date else ""
                
                admin_url = reverse('admin:inventory_container_change', args=[container.pk])

                batches[batch_ref][item_name].append({
                    'id': container.pk,
                    'type': 'container',
                    'transaction_type': 'IN',
                    'quantity': float(container.total_weight_container or 0),
                    'booking_in_quantity': float(container.total_weight_container or 0),
                    'transaction_date': container.booking_in_date.isoformat() if container.booking_in_date else (container.eta.isoformat() if container.eta else None),
                    'supplier_name': container.supplier.name if container.supplier else '',
                    'batch_ref': batch_ref,
                    'usage_notes': container.comments or '',
                    'category_id': cat_id,
                    'sub_category_id': subcat_id,
                    'unit_of_measure': str(container.stock_item.unit_of_measure) if container.stock_item and container.stock_item.unit_of_measure else 'Unit',
                    'warehouse': container.warehouse.warehouse_name if container.warehouse else '',
                    'prod_batch': '',
                    'edit_url': admin_url,
                })

            # THEN ADD STOCK TRANSACTIONS (existing code)
            for trans in StockTransaction.objects.filter(**base_filter).select_related(
                'stock_item',
                'stock_item__category',
                'stock_item__sub_category',
                'stock_item__unit_of_measure',
                'warehouse',
                'supplier'
            ):
                batch_ref = trans.batch_ref or 'Unbatched'
                item_name = str(trans.stock_item) if trans.stock_item else 'Unknown'

                if batch_ref not in batches:
                    batches[batch_ref] = {}
                if item_name not in batches[batch_ref]:
                    batches[batch_ref][item_name] = []

                # GET CORRECT CATEGORY FROM STOCK ITEM
                stock_item = trans.stock_item
                cat_id = stock_item.category.id if stock_item and stock_item.category else None
                subcat_id = stock_item.sub_category.id if stock_item and stock_item.sub_category else None

                # For OUT: supplier/warehouse from original IN transaction with same batch_ref
                supplier_name = trans.supplier.name if trans.supplier else ''
                warehouse_name = trans.warehouse.warehouse_name if trans.warehouse else ''
                if trans.transaction_type == 'OUT':
                    original_in = StockTransaction.objects.filter(
                        batch_ref=batch_ref,
                        transaction_type='IN'
                    ).order_by('pk').first()
                    if original_in:
                        if original_in.supplier:
                            supplier_name = original_in.supplier.name
                        if original_in.warehouse:
                            warehouse_name = original_in.warehouse.warehouse_name
                            
                batches[batch_ref][item_name].append({
                    'id': trans.pk,
                    'type': 'transaction',
                    'transaction_type': trans.transaction_type,
                    'quantity': float(trans.quantity) if trans.quantity else 0,
                    'transaction_date': trans.transaction_date.isoformat() if trans.transaction_date else None,
                    'supplier_name': supplier_name,
                    'batch_ref': batch_ref,
                    'usage_notes': trans.usage_notes or '',
                    'category_id': cat_id,
                    'sub_category_id': subcat_id,
                    'unit_of_measure': str(stock_item.unit_of_measure) if stock_item and stock_item.unit_of_measure else 'Unit',
                    'warehouse': warehouse_name,
                    'prod_batch': '',
                })

            # ✅ ADD MANUFACTURING USAGE DATA - SAME WINDOW AS INVENTORY
            from manufacturing.models import BatchContainer, Batch
            from inventory.models import PackagingBalance, RecipeStockItemBalance
            
            # Get all unique production dates (✅ FILTERED BY SITE via stock_item for PB/RSIB, container for BC)
            prod_dates = set()
            pb_qs = PackagingBalance.objects.all()
            rsib_qs = RecipeStockItemBalance.objects.all()
            bc_qs = BatchContainer.objects.all()
            if current_site:
                pb_qs = pb_qs.filter(stock_item__site=current_site)
                rsib_qs = rsib_qs.filter(stock_item__site=current_site)
                bc_qs = bc_qs.filter(container__site=current_site)  # Filter through container relationship
            
            prod_dates.update(pb_qs.values_list('production_date', flat=True))
            prod_dates.update(rsib_qs.values_list('production_date', flat=True))
            prod_dates.update(bc_qs.values_list('production_date', flat=True))
            
            for prod_date in prod_dates:
                if not prod_date:
                    continue
                    
                prod_date_str = prod_date.isoformat()
                
                # ===== COMBINED: ADD OPENING + CURRENT PRODUCTION (PACKAGING) =====
                packaging_transactions = {}

                # Helper function for batch_ref logic
                def get_batch_ref_from_packaging(balance_record):
                    if balance_record.batch_ref:
                        return balance_record.batch_ref
                    latest_in = StockTransaction.objects.filter(
                        stock_item=balance_record.stock_item, transaction_type='IN'
                    ).order_by('-transaction_date', '-pk').first()
                    return latest_in.batch_ref if latest_in and latest_in.batch_ref else "Unbatched"

                # Loop over all balance records for the current production date (✅ FILTERED BY SITE via stock_item)
                pb_qs_current = PackagingBalance.objects.filter(production_date=prod_date).select_related('stock_item')
                if current_site:
                    pb_qs_current = pb_qs_current.filter(stock_item__site=current_site)
                
                for pb_current in pb_qs_current:
                    stock_item = pb_current.stock_item
                    if not stock_item:
                        continue
                    
                    item_name = str(stock_item)

                    # --- 1. Add the current day's usage (Booked Out - Closing Balance) ---
                    latest_out = StockTransaction.objects.filter(
                        stock_item=stock_item, transaction_type='OUT', transaction_date__lte=prod_date,
                    ).order_by('-transaction_date', '-pk').first()
                    
                    booked_out = Decimal(str(latest_out.quantity)) if latest_out else Decimal('0')
                    closing_balance = pb_current.closing_balance or Decimal('0')
                    current_usage_qty = booked_out - closing_balance
                    
                    if current_usage_qty > 0:
                        batch_ref = get_batch_ref_from_packaging(pb_current)
                        
                        key = (batch_ref, item_name)
                        if key not in packaging_transactions:
                            packaging_transactions[key] = {
                                'batch_ref': batch_ref,
                                'item_name': item_name,
                                'stock_item': stock_item,
                                'total_quantity': Decimal('0'),
                            }
                        packaging_transactions[key]['total_quantity'] += current_usage_qty

                    # --- 2. Conditionally add the opening balance ---
                    # Check the flag on the CURRENT day's record to decide.
                    if not pb_current.cancel_opening_use_bookout:
                        # If not cancelled, find the most recent previous closing balance to use as opening.
                        pb_previous_qs = PackagingBalance.objects.filter(
                            stock_item=stock_item,
                            production_date__lt=prod_date
                        )
                        if current_site:
                            pb_previous_qs = pb_previous_qs.filter(stock_item__site=current_site)
                        pb_previous = pb_previous_qs.order_by('-production_date').first()

                        if pb_previous and pb_previous.closing_balance and pb_previous.closing_balance > 0:
                            opening_balance_qty = pb_previous.closing_balance
                            
                            # Use the batch_ref from the PREVIOUS day's record for this opening quantity.
                            batch_ref = get_batch_ref_from_packaging(pb_previous)
                            key = (batch_ref, item_name)
                            if key not in packaging_transactions:
                                packaging_transactions[key] = {
                                    'batch_ref': batch_ref,
                                    'item_name': item_name,
                                    'stock_item': stock_item,
                                    'total_quantity': Decimal('0'),
                                }
                            packaging_transactions[key]['total_quantity'] += opening_balance_qty

                # 3. ADD ALL COMBINED TRANSACTIONS TO BATCHES (✅ FILTERED BY SITE)
                mfg_batches_qs = Batch.objects.filter(production_date=prod_date)
                if current_site:
                    mfg_batches_qs = mfg_batches_qs.filter(site=current_site)
                mfg_batches = mfg_batches_qs.values_list('batch_number', flat=True)
                prod_batch_ref = ', '.join(mfg_batches) if mfg_batches else ''

                for (batch_ref, item_name), data in packaging_transactions.items():
                    # ✅ If batch_ref contains "/", use SECOND part (Toets 2 Pallet)
                    if '/' in batch_ref:
                        individual_batch_ref = batch_ref.split('/')[1].strip()  # ← SECOND part, not first
                    else:
                        individual_batch_ref = batch_ref
                    
                    if individual_batch_ref not in batches:
                        batches[individual_batch_ref] = {}
                    if item_name not in batches[individual_batch_ref]:
                        batches[individual_batch_ref][item_name] = []
                    
                    cat_id = data['stock_item'].category.id if data['stock_item'].category else None
                    subcat_id = data['stock_item'].sub_category.id if data['stock_item'].sub_category else None
                    
                    batches[individual_batch_ref][item_name].append({
                        'id': f"pkg-{batch_ref}-{item_name}",
                        'type': 'manufacturing',
                        'transaction_type': 'OUT',
                        'quantity': float(data['total_quantity']),
                        'transaction_date': prod_date_str,
                        'supplier_name': '',
                        'batch_ref': batch_ref,
                        'usage_notes': 'Production Out',
                        'category_id': cat_id,
                        'sub_category_id': subcat_id,
                        'unit_of_measure': str(data['stock_item'].unit_of_measure) if data['stock_item'].unit_of_measure else 'Unit',
                        'warehouse': '',
                        'prod_batch': prod_batch_ref,
                    })
            
                # =================================================================================
                recipe_transactions = {}

                # A helper to get batch_ref consistently, re-using the original code's logic.
                def get_batch_ref_from_record(balance_record):
                    if balance_record.batch_ref:
                        return balance_record.batch_ref
                    # Fallback to finding the latest 'IN' transaction's batch_ref
                    latest_in = StockTransaction.objects.filter(
                        stock_item=balance_record.stock_item, transaction_type='IN'
                    ).order_by('-transaction_date', '-pk').first()
                    return latest_in.batch_ref if latest_in and latest_in.batch_ref else "Unbatched"

                # Loop over all balance records for the current production date (✅ FILTERED BY SITE via stock_item)
                rb_qs_current = RecipeStockItemBalance.objects.filter(production_date=prod_date).select_related('stock_item')
                if current_site:
                    rb_qs_current = rb_qs_current.filter(stock_item__site=current_site)
                
                for rb_current in rb_qs_current:
                    stock_item = rb_current.stock_item
                    item_name = str(stock_item)

                    # --- 1. Add the current day's usage (Booked Out - Closing Balance) ---
                    current_usage_qty = (rb_current.booked_out_stock or Decimal('0')) - (rb_current.closing_balance or Decimal('0'))
                    
                    if current_usage_qty > 0:
                        batch_ref = get_batch_ref_from_record(rb_current)
                        
                        # The batch_ref might be a combined string like "BalanceBatch / BookedBatch".
                        # We will use the full string as the key to group transactions.
                        key = (batch_ref, item_name)
                        if key not in recipe_transactions:
                            recipe_transactions[key] = {
                                'batch_ref': batch_ref,
                                'item_name': item_name,
                                'stock_item': stock_item,
                                'total_quantity': Decimal('0'),
                            }
                        recipe_transactions[key]['total_quantity'] += current_usage_qty

                    # --- 2. Conditionally add the opening balance ---
                    # Check the flag on the CURRENT day's record to decide.
                    if not rb_current.cancel_opening_use_bookout:
                        # If not cancelled, find the most recent previous closing balance to use as opening.
                        rb_previous = RecipeStockItemBalance.objects.filter(
                            stock_item=stock_item,
                            production_date__lt=prod_date
                        ).order_by('-production_date').first()

                        if rb_previous and rb_previous.closing_balance and rb_previous.closing_balance > 0:
                            opening_balance_qty = rb_previous.closing_balance
                            
                            # Use the batch_ref from the PREVIOUS day's record for this opening quantity.
                            batch_ref = get_batch_ref_from_record(rb_previous)
                            key = (batch_ref, item_name)
                            if key not in recipe_transactions:
                                recipe_transactions[key] = {
                                    'batch_ref': batch_ref,
                                    'item_name': item_name,
                                    'stock_item': stock_item,
                                    'total_quantity': Decimal('0'),
                                }
                            recipe_transactions[key]['total_quantity'] += opening_balance_qty

                # =================================================================================
                # ===== REVISED LOGIC FOR RECIPE/INGREDIENTS - END REPLACEMENT ======================
                # =================================================================================

                # 3. ADD ALL COMBINED TRANSACTIONS TO BATCHES
                # (This next part of your original code is correct and does not need to be changed)
                mfg_batches_qs = Batch.objects.filter(production_date=prod_date)
                if current_site:
                    mfg_batches_qs = mfg_batches_qs.filter(site=current_site)
                mfg_batches = mfg_batches_qs.values_list('batch_number', flat=True)
                              
                prod_batch_ref = ', '.join(mfg_batches) if mfg_batches else ''

                for (batch_ref, item_name), data in recipe_transactions.items():
                    # ✅ If batch_ref contains "/", use SECOND part
                    if '/' in batch_ref:
                        individual_batch_ref = batch_ref.split('/')[1].strip()
                    else:
                        individual_batch_ref = batch_ref
                    
                    if individual_batch_ref not in batches:
                        batches[individual_batch_ref] = {}
                    if item_name not in batches[individual_batch_ref]:
                        batches[individual_batch_ref][item_name] = []
                    
                    cat_id = data['stock_item'].category.id if data['stock_item'].category else None
                    subcat_id = data['stock_item'].sub_category.id if data['stock_item'].sub_category else None
                    
                    batches[individual_batch_ref][item_name].append({
                        'id': f"recipe-{batch_ref}-{item_name}",
                        'type': 'manufacturing',
                        'transaction_type': 'OUT',
                        'quantity': float(data['total_quantity']),
                        'transaction_date': prod_date_str,
                        'supplier_name': '',
                        'batch_ref': batch_ref,
                        'usage_notes': 'Production Out',
                        'category_id': cat_id,
                        'sub_category_id': subcat_id,
                        'unit_of_measure': str(data['stock_item'].unit_of_measure) if data['stock_item'].unit_of_measure else 'Unit',
                        'warehouse': '',
                        'prod_batch': prod_batch_ref,
                    })

                    
                # === SOURCE 3: BATCH CONTAINER (MEAT) === (✅ FILTERED BY SITE via container or batch)
                bc_qs_prod = BatchContainer.objects.filter(production_date=prod_date)
                if current_site:
                    # Allow either: 1) Import containers with matching site, OR 2) Local containers (no container FK)
                    from django.db.models import Q
                    bc_qs_prod = bc_qs_prod.filter(
                        Q(container__site=current_site) | Q(container__isnull=True)
                    )
                
                for bc in bc_qs_prod:
                    # ✅ HANDLE BOTH IMPORT (with container FK) AND LOCAL (without container)
                    if bc.container:
                        # IMPORT CONTAINER
                        stock_item = bc.container.stock_item
                        if not stock_item:
                            continue
                        batch_ref = bc.container.container_number
                    elif bc.batch_ref:
                        # LOCAL CONTAINER - Use batch_ref as the key (Rain2045)
                        # You need to determine which stock_item this LOCAL container uses
                        # Assuming LOCAL containers are always MEAT - adjust if different
                        
                        # Get the main meat stock item from product
                        from manufacturing.models import Batch
                        batch_qs = Batch.objects.filter(production_date=prod_date)
                        if current_site:
                            batch_qs = batch_qs.filter(site=current_site)
                        batch = batch_qs.first()
                        if batch and batch.product:
                            main_comp = batch.product.main_product_components.first()
                            stock_item = main_comp.stock_item if main_comp else None
                        else:
                            stock_item = None
                        
                        if not stock_item:
                            continue
                        
                        batch_ref = bc.batch_ref  # Use Rain2045 as batch_ref
                    else:
                        # Neither container nor batch_ref - skip
                        continue
                    
                    item_name = str(stock_item)
                    usage_qty = bc.kg_frozen_meat_used or Decimal('0')
                    
                    if batch_ref not in batches:
                        batches[batch_ref] = {}
                    if item_name not in batches[batch_ref]:
                        batches[batch_ref][item_name] = []
                    
                    cat_id = stock_item.category.id if stock_item.category else None
                    subcat_id = stock_item.sub_category.id if stock_item.sub_category else None
                    
                    # Get batch numbers (✅ FILTERED BY SITE)
                    mfg_batches_qs = Batch.objects.filter(production_date=prod_date)
                    if current_site:
                        mfg_batches_qs = mfg_batches_qs.filter(site=current_site)
                    mfg_batches = mfg_batches_qs.values_list('batch_number', flat=True)
                    prod_batch_ref = ', '.join(mfg_batches) if mfg_batches else ''
                    
                    if usage_qty > 0:
                        batches[batch_ref][item_name].append({
                            'id': f"meat-{bc.id}",
                            'type': 'manufacturing',
                            'transaction_type': 'OUT',
                            'quantity': float(usage_qty),
                            'transaction_date': prod_date_str,
                            'supplier_name': '',
                            'batch_ref': batch_ref,  # ← Rain2045 for LOCAL, TTN8099285 for IMPORT
                            'usage_notes': 'Production OUT',
                            'category_id': cat_id,
                            'sub_category_id': subcat_id,
                            'unit_of_measure': str(stock_item.unit_of_measure) if stock_item.unit_of_measure else 'Unit',
                            'warehouse': '',
                            'prod_batch': prod_batch_ref,
                        })


            # AMENDMENTS FROM BOTH STOCK TRANSACTIONS AND CONTAINERS (✅ FILTERED BY SITE)
            amendments_qs = Amendment.objects.select_related(
                'stock_item',
                'stock_item__category',
                'stock_item__sub_category',
                'stock_item__unit_of_measure'
            )
            # ✅ Filter amendments by stock_item's site (Amendment doesn't have site field)
            if current_site:
                amendments_qs = amendments_qs.filter(stock_item__site=current_site)
            
            for amend in amendments_qs:
                batch_ref = amend.batch_ref or 'Unbatched'
                
                # Find the correct item_name to merge with - check if batch_ref already exists in batches
                # If so, use the first existing item_name from that batch (so amendments merge with transactions)
                item_name = None
                stock_item = None
                
                if batch_ref in batches and batches[batch_ref]:
                    # Use the first item_name already in this batch (from transactions)
                    item_name = list(batches[batch_ref].keys())[0]
                    # Get category/subcat from that entry
                    first_entry = batches[batch_ref][item_name][0]
                    cat_id = first_entry.get('category_id')
                    subcat_id = first_entry.get('sub_category_id')
                    unit_measure = first_entry.get('unit_of_measure', 'Unit')
                else:
                    # Batch doesn't exist yet - use amendment's stock_item if available
                    if amend.stock_item:
                        stock_item = amend.stock_item
                        item_name = str(stock_item)
                        cat_id = stock_item.category.id if stock_item.category else None
                        subcat_id = stock_item.sub_category.id if stock_item.sub_category else None
                        unit_measure = str(stock_item.unit_of_measure) if stock_item.unit_of_measure else 'Unit'
                    else:
                        # No stock_item on amendment and no existing batch - skip
                        continue

                if batch_ref not in batches:
                    batches[batch_ref] = {}
                if item_name not in batches[batch_ref]:
                    batches[batch_ref][item_name] = []

                batches[batch_ref][item_name].append({
                    'id': amend.pk,
                    'type': 'amendment',
                    'amendment_type': amend.amendment_type,
                    'quantity': float(amend.quantity) if amend.quantity else 0,
                    'date': amend.date.isoformat() if amend.date else None,
                    'reason': amend.reason or '',
                    'category_id': cat_id,
                    'sub_category_id': subcat_id,
                    'unit_of_measure': unit_measure,
                    'warehouse': '',
                    'supplier_name': '',
                    'prod_batch': '',
                })

            # Get categories for filtering (✅ FILTERED BY SITE)
            categories_qs = StockCategory.objects.prefetch_related('subcategories')
            if current_site:
                categories_qs = categories_qs.filter(site=current_site)
            
            categories = []
            for cat in categories_qs:
                sub_cats = [{'id': s.id, 'name': s.name} for s in cat.subcategories.all()]
                categories.append({
                    'id': cat.id,
                    'name': cat.name,
                    'subcategories': sub_cats,
                })
                
            filtered_batches = {}
            for batch_ref, items_data in batches.items():
                for item_name, entries in items_data.items():
                    # Check if this item has at least one matching StockTransaction OR Container
                    has_matching_entry = any(
                        e['type'] in ('transaction', 'container')
                        for e in entries
                    )
                    
                    if has_matching_entry:
                        if batch_ref not in filtered_batches:
                            filtered_batches[batch_ref] = {}
                        filtered_batches[batch_ref][item_name] = entries

            batches = filtered_batches  # Replace with filtered version

            data_json = json.dumps({
                'grouped_by_batch': batches,
                'categories_data': categories
            })

            data_json = json.dumps({
                'grouped_by_batch': batches,
                'categories_data': categories
            })

            if hasattr(response, 'render'):
                response.render()

            injection = f"""
            <div class="results-content"></div>
            <script src="/static/js/inventory-changelist.js"></script>
            <script>
            window.DATA = {data_json};
            </script>
            """.encode('utf-8')

            response.content = response.content.replace(
                b'</body>',
                injection + b'</body>'
            )

        except Exception as e:
            import traceback
            traceback.print_exc()

        return response
        
    def unit_of_measure_display(self, obj):
        if obj and obj.pk:
            if obj.stock_item and obj.stock_item.unit_of_measure:
                return str(obj.stock_item.unit_of_measure)
        return "-"

    unit_of_measure_display.short_description = "Unit of Measure"



    def _redirect_to_next(self, request, default_response, obj_id=None):
        """
        If ?next=... is present (or posted), redirect there after save.
        Also check for ?back_url= and session for stored referrer.
        Only applies if NOT saving and continuing.
        """
        # If user clicked "Save and continue editing", return default (stay on form)
        if '_continue' in request.POST:
            return default_response
        
        # Priority 1: Check for 'next' parameter (already being used by system)
        next_url = request.GET.get('next') or request.POST.get('next')
        if next_url:
            return redirect(next_url)
        
        # Priority 2: Check for back_url parameter
        back_url = request.GET.get('back_url', '') or request.POST.get('back_url', '')
        if back_url:
            return redirect(back_url)
        
        # Priority 3: Check session for stored referrer
        if obj_id:
            session_key = f'stocktransaction_referrer_{obj_id}'
            stored_referrer = request.session.get(session_key, '')
            if stored_referrer:
                return redirect(stored_referrer)
        
        return default_response

    def response_change(self, request, obj):
        default = super().response_change(request, obj)
        return self._redirect_to_next(request, default, obj.pk)

    def response_add(self, request, obj, post_url_continue=None):
        default = super().response_add(request, obj, post_url_continue)
        return self._redirect_to_next(request, default, obj.pk)

    class Media:
        js = (
            'js/booking_live_calc.js',
            'js/stocktransaction_form_toggle.js',
            'js/unit_autofill_stocktransaction.js', 
            'js/trigger_unit_on_load.js',
            'js/prod_batch_autofill.js',
        )
        css = {
            'all': ('css/inventory-changelist.css',)
        }

class FinalProductBookInForm(forms.ModelForm):
    date = forms.DateField(
        required=True,
        label="Transaction Date",
        widget=admin_widgets.AdminDateWidget,
        input_formats=['%d-%m-%Y', '%Y-%m-%d', '%d/%m/%Y', '%d.%m.%Y'],
    )
    
    production_date = forms.DateField(
        required=True,
        label="Production Date",
        widget=admin_widgets.AdminDateWidget,
        input_formats=['%d-%m-%Y', '%Y-%m-%d', '%d/%m/%Y', '%d.%m.%Y'],
    )

    per_batch_placeholder = forms.CharField(
        required=False,
        label='',
        widget=forms.HiddenInput,
    )

    to_warehouse = forms.ModelChoiceField(
        queryset=Warehouse.objects.none(),
        required=False,
        widget=forms.Select(),
        label="Warehouse",
    )

    class Meta:
        model = FinishedProductTransaction
        fields = [
            'date',
            'production_date',
            'batch',
            'per_batch_placeholder',
            'to_warehouse',
            'authorized_person',
            'notes',
        ]

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        # Ensure queryset + label for both ADD and VIEW
        if "to_warehouse" in self.fields:
            self.fields["to_warehouse"].queryset = Warehouse.objects.all()
            self.fields["to_warehouse"].label = "Warehouse"

        # Not required on existing objects
        if getattr(self.instance, "pk", None):
            if "production_date" in self.fields:
                self.fields["production_date"].required = False

        # Always guard access to batch
        if "batch" in self.fields:
            self.fields["batch"].required = False
            # ✅ FIX: Filter batch by production_date and current site
            current_site = getattr(self.request, 'current_site', None) if self.request else None
            
            # If editing existing object, show its batch + all batches for that production date
            if getattr(self.instance, "pk", None) and self.instance.batch:
                prod_date = self.instance.batch.production_date
                batch_qs = Batch.objects.filter(production_date=prod_date)
                if current_site:
                    batch_qs = batch_qs.filter(site=current_site)
                self.fields["batch"].queryset = batch_qs
            else:
                # New object - start with empty, will be populated by production_date selection
                self.fields["batch"].queryset = Batch.objects.none()

        if self.request and self.request.method == "GET" and not self.instance.pk:
            get = self.request.GET

            batch_code = get.get("batch")
            if batch_code and "batch" in self.fields:
                try:
                    batch = Batch.objects.get(batch_number=batch_code)
                    self.initial["batch"] = batch
                    if batch.production_date:
                        self.initial["production_date"] = batch.production_date
                        # ✅ FIX: Filter batch by site when batch is passed
                        current_site = getattr(self.request, 'current_site', None)
                        batch_qs = Batch.objects.filter(production_date=batch.production_date)
                        if current_site:
                            batch_qs = batch_qs.filter(site=current_site)
                        self.fields["batch"].queryset = batch_qs
                except Batch.DoesNotExist:
                    pass

            tx_type = get.get("transaction_type")
            if tx_type and "transaction_type" in self.fields:
                self.initial["transaction_type"] = tx_type

            from_wh = get.get("from_warehouse")
            if from_wh and "from_warehouse" in self.fields:
                self.initial["from_warehouse"] = from_wh

            prod_name = get.get("product_name")
            if prod_name and "product_name" in self.fields:
                self.initial["product_name"] = prod_name

            size = get.get("size")
            if size and "size" in self.fields:
                self.initial["size"] = size

            auth = get.get("authorized_person")
            if auth and "authorized_person" in self.fields:
                self.initial["authorized_person"] = auth
    
    def clean(self):
        cleaned = super().clean()
        request = getattr(self, 'request', None)

        if not request or self.instance.pk:
            return cleaned

        duplicate_batches = []

        from .models import Batch, FinishedProductTransaction

        for key, val in request.POST.items():
            if not key.startswith("multi_batch_"):
                continue

            batch_number = key.replace("multi_batch_", "")
            qty_key = f"multi_qty_{batch_number}"
            raw_qty = request.POST.get(qty_key)
            if not raw_qty:
                continue

            try:
                qty = Decimal(raw_qty)
            except Exception:
                continue

            if qty <= 0:
                continue

            try:
                batch = Batch.objects.get(batch_number=batch_number)
            except Batch.DoesNotExist:
                continue

            if FinishedProductTransaction.objects.filter(
                batch=batch,
                transaction_type="IN",
            ).exists():
                duplicate_batches.append(batch_number)

        if duplicate_batches:
            batch_list = ", ".join(duplicate_batches)
            raise ValidationError(
                _("The following batches already have a Book In transaction: %(batches)s"),
                code="duplicate_batch_in",
                params={"batches": batch_list},
            )

        return cleaned

    class Media:
        js = ('js/final_product_batch_filter.js',)

class FinalProductMovementForm(forms.ModelForm):
    date = forms.DateField(
        required=True,
        label="Transaction Date",
        widget=admin_widgets.AdminDateWidget,
        input_formats=['%d-%m-%Y', '%Y-%m-%d', '%d/%m/%Y', '%d.%m.%Y'],
    )
    
    class Meta:
        model = FinishedProductTransaction
        fields = [
            "date",
            "batch",
            "product_name",
            "size",
            "transaction_type",
            "quantity",
            "from_warehouse",
            "to_warehouse",
            "client",
            "authorized_person",
            "notes",
        ]

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        # ---------- ADD view: prefill from GET ----------
        if self.request and self.request.method == "GET" and not self.instance.pk:
            get = self.request.GET

            # Batch handling (convert PK string to object)
            batch_code = get.get("batch")
            if batch_code and "batch" in self.fields:
                try:
                    batch = Batch.objects.get(pk=batch_code)  # pk from URL
                    self.initial["batch"] = batch
                except Batch.DoesNotExist:
                    pass

            # From warehouse (convert PK string to object)
            from_wh = get.get("from_warehouse")
            if from_wh and "from_warehouse" in self.fields:
                try:
                    wh = Warehouse.objects.get(pk=from_wh)
                    self.initial["from_warehouse"] = wh
                except Warehouse.DoesNotExist:
                    pass

            # Product details and other params
            prod_name = get.get("product_name")
            if prod_name and "product_name" in self.fields:
                self.initial["product_name"] = prod_name

            size = get.get("size")
            if size and "size" in self.fields:
                self.initial["size"] = size

            # Transaction type
            tx_type = get.get("transaction_type")
            if tx_type and "transaction_type" in self.fields:
                self.initial["transaction_type"] = tx_type

            # Authorized person blank for new movements
            if "authorized_person" in self.fields:
                self.initial["authorized_person"] = ""

        # ---------- Show to_warehouse only for TRANSFER ----------
        tx_type = None

        # Prefer instance value (change view)
        if getattr(self.instance, "pk", None):
            tx_type = self.instance.transaction_type

        # On add view, fall back to GET / initial
        if not tx_type and self.request and self.request.method == "GET":
            tx_type = self.request.GET.get("transaction_type") or self.initial.get("transaction_type")

        # Hide to_warehouse unless this is a TRANSFER
        if "to_warehouse" in self.fields and tx_type != "TRANSFER":
            self.fields["to_warehouse"].widget = HiddenInput()

        # Hide client unless this is a DISPATCH
        if "client" in self.fields and tx_type != "DISPATCH":
            self.fields["client"].widget = HiddenInput()

    class Media:
        js = ('js/booking_live_calc.js',)

@admin.register(FinishedProductTransaction)
class FinalProductAdmin(SiteAwareModelAdmin, ArchivableAdmin):
    search_fields = ['batch__batch_number', 'product_name']
    change_form_template = "admin/inventory/change_form.html"
    form = FinalProductBookInForm  # default for IN

    # ------- form injection with request -------

    def get_form(self, request, obj=None, **kwargs):
        # Decide transaction_type for this request
        if obj is not None:
            tx_type = obj.transaction_type
        else:
            tx_type = request.GET.get("transaction_type") or "IN"

        if tx_type in ["DISPATCH", "TRANSFER", "SCRAP"]:
            kwargs["form"] = FinalProductMovementForm
        else:
            kwargs["form"] = FinalProductBookInForm

        form_class = super().get_form(request, obj, **kwargs)

        def form_with_request(*args, **kw):
            kw["request"] = request
            return form_class(*args, **kw)

        return form_with_request

    # ------- list display -------

    list_display = (
        'production_date_display',
        'batch',
        'product_name',
        'size',
        'direction_display',  
        'transaction_type_display',
        'status_display',
        'stock_released_display',
        'bookin_ready_display',
        'movement_quantity_display',
        'warehouse_display',
        'client',
        'transaction_date_display',
    )

    readonly_fields = (
        "product_name",
        "size",
        "transaction_type",
        "ready_to_dispatch_display",
        "bookin_ready_display", 
        "status",        
    )
    
    list_filter = (
        ('batch__production_date', admin.DateFieldListFilter),
        'transaction_type',
    )
    
    list_display_links = ('transaction_type_display',)
    
    def transaction_date_display(self, obj):
        """
        Show stock_released_date for DISPATCH transactions (when released),
        otherwise show regular date
        """
        if obj.transaction_type == 'DISPATCH' and obj.stock_released_date:
            return obj.stock_released_date
        return obj.date

    transaction_date_display.short_description = "Transaction Date"
    transaction_date_display.admin_order_field = 'date'

    def status_display(self, obj):
        """Display status only for DISPATCH transactions"""
        if obj.transaction_type == 'DISPATCH':
            return obj.get_status_display()
        return "-"

    status_display.short_description = "Status"

    # ------- list helpers -------
    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        obj = self.get_object(request, object_id)

        # Default
        title = "View Book in Final product"

        if obj and obj.transaction_type == "DISPATCH":
            title = "Dispatch Final product"
        elif obj and obj.transaction_type == "TRANSFER":
            title = "Stock transfer Final product"
        elif obj and obj.transaction_type == "SCRAP":
            title = "Damage / Scrap Final product"

        extra_context["page_title"] = title

        response = super().change_view(request, object_id, form_url, extra_context)

        return response
    
    def production_date_display(self, obj):
        if obj.batch and getattr(obj.batch, "production_date", None):
            return obj.batch.production_date.strftime("%d/%m/%y")
        return "-"

    production_date_display.short_description = "Production Date"
    production_date_display.admin_order_field = 'batch__production_date'

    def transaction_date_display(self, obj):
        """
        Show stock_released_date for DISPATCH (when released), otherwise regular date
        """
        if obj.transaction_type == 'DISPATCH' and obj.stock_released_date:
            return obj.stock_released_date.strftime("%d/%m/%y")
        return obj.date.strftime("%d/%m/%y") if obj.date else "-"

    transaction_date_display.short_description = "Transaction Date"
    transaction_date_display.admin_order_field = 'date'
    
    def warehouse_display(self, obj):
        # For IN: use to_warehouse (where stock is booked in)
        if obj.transaction_type == "IN":
            return obj.to_warehouse
        
        # For TRANSFER: show destination warehouse (to_warehouse)
        elif obj.transaction_type == "TRANSFER":
            return obj.to_warehouse or obj.from_warehouse
        
        # For DISPATCH/SCRAP: show source warehouse (from_warehouse)
        return obj.from_warehouse or obj.to_warehouse

    warehouse_display.short_description = "Warehouse"

    warehouse_display.short_description = "Warehouse"
    
    def movement_quantity_display(self, obj):
        # only show qty for movement types, hide for IN
        if obj.transaction_type in ("DISPATCH", "TRANSFER", "SCRAP"):
            return f"{obj.quantity:.0f}"
        return ""
    movement_quantity_display.short_description = "Quantity"
    movement_quantity_display.admin_order_field = "quantity"
    
    def bookin_ready_display(self, obj):
        """
        Show progressive balance as of this transaction's effective date.
        Book In: shows starting quantity
        All other rows: show available AS OF that transaction's effective date
        """
        if not getattr(obj, "batch_id", None):
            return ""

        from .models import FinishedProductTransaction
        from django.db.models import Sum
        from decimal import Decimal

        # Get the Book In transaction's ready_to_dispatch (starting balance)
        in_tx = (
            FinishedProductTransaction.objects
            .filter(batch=obj.batch, transaction_type="IN")
            .order_by("pk")
            .first()
        )
        
        if not in_tx or in_tx.ready_to_dispatch is None:
            return ""
        
        # For Book In row, show the starting balance
        if obj.transaction_type == "IN":
            return f"{in_tx.ready_to_dispatch:.0f}"
        
        starting_qty = Decimal(str(in_tx.ready_to_dispatch))
        
        # ✅ Determine effective date for THIS row
        if obj.transaction_type == 'DISPATCH' and obj.stock_released_date:
            effective_date = obj.stock_released_date
        else:
            effective_date = obj.date
        
        # ✅ Count dispatches RELEASED on or before the effective date
        total_dispatched = FinishedProductTransaction.objects.filter(
            batch=obj.batch,
            transaction_type='DISPATCH',
            status='RELEASED',
            stock_released_date__isnull=False,
            stock_released_date__lte=effective_date
        ).aggregate(total=Sum('quantity'))['total'] or Decimal('0')
        
        # ✅ Count scrap on or before the effective date
        total_scrapped = FinishedProductTransaction.objects.filter(
            batch=obj.batch,
            transaction_type='SCRAP',
            date__lte=effective_date
        ).aggregate(total=Sum('quantity'))['total'] or Decimal('0')
        
        # Balance as of this transaction's effective date
        balance = starting_qty - total_dispatched - total_scrapped
        
        return f"{balance:.0f}"

    bookin_ready_display.short_description = "Ready to Dispatch"


    def transaction_type_display(self, obj):
        url = reverse(
            'admin:inventory_finishedproducttransaction_change',
            args=[obj.pk]
        )
        trans_type = obj.get_transaction_type_display()
        return format_html(
            '<a href="{}" style="color: #417690; text-decoration: none; font-weight: bold;">{}</a>',
            url,
            trans_type
        )
    transaction_type_display.short_description = "Transaction type"

    def available_for_batch_display(self, obj):
        if not getattr(obj, "batch_id", None):
            return ""
        return f"{obj.available_qty_for_batch:.2f}"

    def ready_to_dispatch_display(self, obj):
        if obj.ready_to_dispatch is None:
            return ""
        return f"{obj.ready_to_dispatch:.0f}"
    ready_to_dispatch_display.short_description = "Ready to Dispatch"
    
    def stock_released_display(self, obj):
        """Display checkmark/cross only for DISPATCH transactions"""
        if obj.transaction_type == 'DISPATCH':
            if obj.stock_released:
                return mark_safe('<img src="/static/admin/img/icon-yes.svg" alt="Yes">')
            else:
                return mark_safe('<img src="/static/admin/img/icon-no.svg" alt="No">')
        return ""  # Empty for all other transaction types

    stock_released_display.short_description = "Y/N"

    # ------- dynamic read-only & fieldsets -------

    def get_readonly_fields(self, request, obj=None):
        base = list(self.readonly_fields)

        # ADD view
        if obj is None:
            tx_type = request.GET.get("transaction_type") or "IN"

            if tx_type == "DISPATCH":
                return base + ["batch", "from_warehouse", "quantity", "client"]
            
            elif tx_type in ["TRANSFER", "SCRAP"]:
                return base + ["batch", "from_warehouse"]

            return base

        # CHANGE view (editing existing record)
        if obj.transaction_type == "IN":
            all_fields = [f.name for f in self.model._meta.fields]
            return list(set(base + all_fields))

        elif obj.transaction_type == "DISPATCH":
            # ✅ All controlled by picking slip
            return base + [
                "batch", 
                "from_warehouse", 
                "transaction_type", 
                "quantity", 
                "client",
                "stock_released",
                "stock_released_date",  # ✅ NEW - readonly
                "released_by_display",
                "notes",
            ]
        
        else:
            return base + ["batch", "from_warehouse", "transaction_type"]
            
    def released_by_display(self, obj):
        """Display authorized_person as 'Released by' for dispatches"""
        return obj.authorized_person or "-"

    released_by_display.short_description = "Released by"

    def get_fieldsets(self, request, obj=None):
        # Determine transaction_type for this page
        if obj is not None:
            tx_type = obj.transaction_type
        else:
            tx_type = request.GET.get("transaction_type") or "IN"

        # ADD view for IN (multi book‑in)
        if obj is None and tx_type == "IN":
            return (
                ("Product Book In", {
                    "fields": (
                        ("date",),
                        ("production_date",),
                        ("per_batch_placeholder",),
                        ("to_warehouse",),
                        ("authorized_person",),
                        ("notes",),
                    ),
                }),
            )

        # DISPATCH view (perfect as is)
        if tx_type == "DISPATCH":
            common = [
                ("stock_released_date", "status",),
                ("batch", "product_name", "size"),
                ("quantity",),
            ]
            
            middle = [
                ("from_warehouse",),
                ("client",),
            ]
            
            release_section = [
                ("stock_released",),  
            ]
            
            tail = [
                ("released_by_display",), 
                ("notes",),  
            ]
            
            return (
                ("Dispatch Final product", {
                    "fields": tuple(common + middle),
                }),
                ("Release Status", {
                    "fields": tuple(release_section),
                    "description": "Controlled by Picking Slip completion" 
                }),
                ("Additional Information", {
                    "fields": tuple(tail),
                }),
            )
        
        # SCRAP view (Damage / Scrap)
        elif tx_type == "SCRAP":
            common = [
                ("date", "transaction_type",),
                ("batch", "product_name", "size"),
                ("bookin_ready_display",), 
            ]
            
            middle = [
                ("from_warehouse",),  # Readonly - pulled from Book In
                ("quantity",),  # Editable - user enters scraped qty
            ]
            
            tail = [
                ("authorized_person",),
                ("notes",),
            ]
            
            return (
                ("Damage / Scrap Final product", {
                    "fields": tuple(common + middle + tail),
                }),
            )
        
        # TRANSFER view
        elif tx_type == "TRANSFER":
            common = [
                ("date", "transaction_type",),
                ("batch", "product_name", "size"),
                ("bookin_ready_display",),  # Show ready to dispatch qty (readonly)
            ]
            
            middle = [
                ("from_warehouse", "to_warehouse"),  # From readonly, To editable
                ("quantity",),  # Editable - user enters transfer qty
            ]
            
            tail = [
                ("authorized_person",),
                ("notes",),
            ]
            
            return (
                ("Stock Transfer Final product", {
                    "fields": tuple(common + middle + tail),
                }),
            )

        # Fallback for existing IN objects (view book‑in)
        return (
            ("Booked In", {
                "fields": (
                    ("date",),
                    ("batch",),
                    ("product_name", "size"),
                    ("ready_to_dispatch_display",),
                    ("to_warehouse",), 
                    ("authorized_person",),
                    ("notes",),
                ),
            }),
        )


    # ------- custom add_view: Save & Continue stays on page -------

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        request.session['finished_transaction_type'] = 'IN'
        extra_context['transaction_type'] = 'IN'

        # Normal flow for non-POST or no _continue
        if request.method != "POST" or "_continue" not in request.POST:
            return super().add_view(request, form_url, extra_context)

        # --- Custom flow for "Save and continue editing" ---
        ModelForm = self.get_form(request)
        form = ModelForm(request.POST, request.FILES, request=request)

        if form.is_valid():
            # dummy obj just to satisfy save_model signature
            obj = self.model()
            self.save_model(request, obj, form, change=False)

            messages.success(
                request,
                _("The multi book-in was saved successfully. You may continue editing."),
            )

            admin_form = admin_helpers.AdminForm(
                form,
                list(self.get_fieldsets(request)),
                self.prepopulated_fields,
                self.get_readonly_fields(request),
                model_admin=self,
            )

            media = self.media + admin_form.media

            context = {
                **self.admin_site.each_context(request),
                "title": _("Add finished product transaction"),
                "adminform": admin_form,
                "is_popup": False,
                "media": media,
                "errors": admin_helpers.AdminErrorList(form, []),
                "app_label": self.model._meta.app_label,
                "opts": self.model._meta,
                "add": True,
                "change": False,
                "has_view_permission": self.has_view_permission(request),
                "has_editable_inline_admin_formsets": False,
                "has_add_permission": self.has_add_permission(request),
                "has_change_permission": self.has_change_permission(request),
                "has_delete_permission": self.has_delete_permission(request),
                "save_as": self.save_as,
                "save_on_top": self.save_on_top,
                "transaction_type": 'IN',
            }
            if extra_context:
                context.update(extra_context)

            request.current_app = self.admin_site.name
            return TemplateResponse(
                request,
                "admin/change_form.html",
                context,
            )

        # If invalid, fall back to normal behavior (shows errors on add form)
        return super().add_view(request, form_url, extra_context)

    # ------- multi-book-in save -------

    def save_model(self, request, obj, form, change):
        if not change:
            prod_date = form.cleaned_data.get("production_date")
            if not prod_date:
                return

            base_date = form.cleaned_data.get("date")
            authorized_person = form.cleaned_data.get("authorized_person")
            notes = form.cleaned_data.get("notes")

            from .models import FinishedProductTransaction  # Batch already imported above

            for key, val in request.POST.items():
                if not key.startswith("multi_batch_"):
                    continue

                batch_number = key.replace("multi_batch_", "")
                qty_key = f"multi_qty_{batch_number}"
                ready_key = f"multi_ready_{batch_number}"
                wh_key = f"multi_wh_{batch_number}"

                raw_qty = request.POST.get(qty_key)
                if not raw_qty:
                    continue

                try:
                    qty = Decimal(raw_qty)
                except Exception:
                    continue

                if qty <= 0:
                    continue

                try:
                    batch = Batch.objects.get(batch_number=batch_number)
                except Batch.DoesNotExist:
                    continue

                to_wh = None
                wh_id = request.POST.get(wh_key)
                if wh_id:
                    try:
                        from commercial.models import Warehouse
                        to_wh = Warehouse.objects.get(pk=wh_id)
                    except (Warehouse.DoesNotExist, ImportError):
                        pass

                tx = FinishedProductTransaction(
                    date=base_date,
                    batch=batch,
                    quantity=qty,
                    transaction_type='IN',
                    to_warehouse=to_wh,
                    authorized_person=authorized_person,
                    notes=notes,
                    site=getattr(request, 'current_site', None),
                )

                if batch.product:
                    tx.product_name = batch.product.product_name or ''
                tx.size = getattr(batch, "size", "") or ""

                raw_ready = request.POST.get(ready_key)
                if raw_ready:
                    try:
                        tx.ready_to_dispatch = Decimal(raw_ready)
                    except Exception:
                        pass

                tx.save()

            return

        return super().save_model(request, obj, form, change)

    # ------- redirects after add (no _continue here) -------

    def response_add(self, request, obj, post_url_continue=None):
        add_url = request.path

        if "_addanother" in request.POST:
            return HttpResponseRedirect(add_url + "?mode=new")

        changelist_url = reverse("admin:inventory_finishedproducttransaction_changelist")
        return HttpResponseRedirect(changelist_url)

    # ------- custom movement buttons handling -------

    def response_change(self, request, obj):
        # Only for IN records with a batch
        if obj.transaction_type == "IN" and obj.batch_id:
            from .models import FinishedProductTransaction

            if "_dispatch_out" in request.POST:
                tx_type = "DISPATCH"
            elif "_transfer" in request.POST:
                tx_type = "TRANSFER"
            elif "_scrap" in request.POST:
                tx_type = "SCRAP"
            else:
                return super().response_change(request, obj)

            # 1) Create the new movement, copying data from the IN obj
            new_tx = FinishedProductTransaction.objects.create(
                date=obj.date,
                batch=obj.batch,
                product_name=obj.product_name,
                size=obj.size,
                transaction_type=tx_type,
                from_warehouse=obj.to_warehouse,  # pull in saved warehouse
                authorized_person="",             # blank as you wanted
                notes="",                         # or obj.notes if you prefer
            )

            # 2) Redirect straight to its change form
            url = reverse(
                "admin:inventory_finishedproducttransaction_change",
                args=[new_tx.pk],
            )
            return HttpResponseRedirect(url)

        return super().response_change(request, obj)

    class Media:
        css = {
            'all': ('css/admin_custom.css',)   # path under STATIC_URL
        }
        js = (
            'js/finishedproduct_multibookin.js',
            'js/finishedproduct_group_by_batch.js',
        )
@admin.register(PickingSlip)
class PickingSlipAdmin(SiteAwareModelAdmin, ArchivableAdmin):
    # Only show the essentials in list view
    list_display = (
        'billing_base_number',
        'billing_date',     
        'due_date',          
        'pdf_link',         
        'completed',
        'released_by',        
        'date_completed',        
        'date_created',        
    )

    list_filter = ('completed', 'billing_date', 'date_created')
    search_fields = ('billing__base_number',)

    readonly_fields = (
        'billing',
        'billing_date',
        'due_date',
        'date_created',
        'date_completed',
        'picking_slip_pdf',
    )

    fieldsets = (
        ('Picking Slip', {
            'fields': (
                'billing',          
                'billing_date',
                'due_date',
                'picking_slip_pdf', 
                'released_by',
                'completed',        
                'date_completed',
                'notes',
            ),
        }),
    )

    # ----- helpers for list_display -----

    def billing_base_number(self, obj):
        # plain text billing number (no link)
        return obj.billing.base_number if obj.billing else "-"
    billing_base_number.short_description = "Billing #"
    billing_base_number.admin_order_field = 'billing__base_number'

    def pdf_link(self, obj):
        if obj.picking_slip_pdf:
            return format_html(
                '<a href="{}" target="_blank" title="View picking slip" '
                'style="font-size:16px;color:#417690;"><i class="fa fa-eye"></i></a>',
                obj.picking_slip_pdf.url,
            )
        return mark_safe('<span style="color:#ccc;">No PDF</span>')
    pdf_link.short_description = "PDF"

    def has_add_permission(self, request):
        # No manual adds, only via signal
        return False


# =============================================================================
# PURCHASE ORDER ADMIN
# =============================================================================

from .models import PurchaseOrder, PurchaseOrderLineItem


class PurchaseOrderLineItemInline(admin.TabularInline):
    model = PurchaseOrderLineItem
    extra = 0
    min_num = 1
    fields = ('category', 'sub_category', 'stock_item', 'quantity', 'unit_price', 'line_total_display_field')
    readonly_fields = ('line_total_display_field',)
    autocomplete_fields = []
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter category and stock_item by current site"""
        current_site = getattr(request, 'current_site', None)
        
        if db_field.name == "category":
            if current_site:
                # Site admin: show ONLY categories for this site
                kwargs["queryset"] = StockCategory.objects.filter(site_id=current_site.id)
            else:
                # HQ context: show all categories
                kwargs["queryset"] = StockCategory.objects.all()
        
        elif db_field.name == "stock_item":
            if current_site:
                # Site admin: show ONLY stock items for this site
                kwargs["queryset"] = StockItem.objects.filter(site_id=current_site.id)
            else:
                # HQ context: show all stock items
                kwargs["queryset"] = StockItem.objects.all()
        
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    def line_total_display_field(self, obj):
        if obj and obj.pk:
            currency = obj.purchase_order.currency if obj.purchase_order else 'R'
            symbols = {'R': 'R', 'NAD': 'N$', 'USD': '$', 'EUR': '€'}
            symbol = symbols.get(currency, currency)
            return f"{symbol} {obj.line_total:,.2f}"
        return "-"
    line_total_display_field.short_description = "Line Total"
    
    class Media:
        js = (
            'js/po_line_item_price.js',  # Will auto-fetch price when stock item selected
        )
        css = {
            'all': ('css/po_admin.css',)
        }


class PurchaseOrderAdminForm(forms.ModelForm):
    # Override date fields with explicit format
    order_date = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'vDateField', 'size': '10'}),
        input_formats=['%d-%m-%Y', '%d/%m/%Y', '%Y-%m-%d'],
    )
    due_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'vDateField', 'size': '10'}),
        input_formats=['%d-%m-%Y', '%d/%m/%Y', '%Y-%m-%d'],
    )
    
    class Meta:
        model = PurchaseOrder
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Filter supplier by site context (isolated, no global sharing)
        if 'supplier' in self.fields:
            current_site = getattr(request, 'current_site', None) if request else None
            if current_site:
                # Site admin: show ONLY suppliers for this site (no cross-site access)
                self.fields['supplier'].queryset = Supplier.objects.filter(site_id=current_site.id)
            else:
                # HQ context - show all suppliers across all sites
                self.fields['supplier'].queryset = Supplier.objects.all()
        
        # Remove the "Today" shortcut from date fields by using plain DateInput
        # Keep default Django admin date widgets (with calendar picker)
        # CSS will hide the "Today" shortcut links


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(SiteAwareModelAdmin, ArchivableAdmin):
    form = PurchaseOrderAdminForm
    
    def get_form(self, request, obj=None, **kwargs):
        """Pass request to form for site-based supplier filtering"""
        kwargs['request'] = request
        return super().get_form(request, obj, **kwargs)
    inlines = [PurchaseOrderLineItemInline]
    change_form_template = 'admin/inventory/purchaseorder/change_form.html'
    
    list_display = (
        'po_number',
        'order_type',
        'order_date_display',
        'due_date_display',
        'supplier',
        'currency',
        'total_display',
        'status',
        'view_po',
        'email_po',
    )
    
    list_filter = ('order_type', 'status', 'currency', 'order_date')
    search_fields = ('po_number', 'supplier__name')
    date_hierarchy = 'order_date'
    ordering = ['-order_date', '-po_number']
    
    fieldsets = (
        ('Order Information', {
            'fields': (
                ('order_type', 'po_number', 'status'),
                ('order_date', 'due_date'),
            ),
        }),
        ('Supplier', {
            
            'fields': (
                'supplier',
            ),
        }),
        ('Totals', {
            'fields': (
                ('currency', 'vat_percentage', 'total_amount_display',),
            ),
        }),
        ('Notes', {
            'fields': (
                'notes',
            ),
            'classes': ('collapse',),
        }),
    )
    
    # Hidden fields - moved to template via block override
    readonly_fields = ('total_amount_display',)
    
    def total_amount_display(self, obj):
        """Display total with a unique ID for JavaScript updates"""
        if obj and obj.pk:
            currency_symbols = {
                'R': 'R',
                'NAD': 'N$',
                'USD': '$',
                'EUR': '€',
            }
            symbol = currency_symbols.get(obj.currency, obj.currency)
            total = sum(item.line_total for item in obj.line_items.all())
            vat_amount = total * (obj.vat_percentage / 100)
            grand_total = total + vat_amount
            formatted = f"{symbol} {grand_total:,.2f}"
        else:
            formatted = "R 0.00"
        
        from django.utils.html import format_html
        return format_html('<span id="po-grand-total-display">{}</span>', formatted)
    total_amount_display.short_description = "Total amount display"
    
    # Hide category/sub_category - they're selected in line items
    # Hide create_po - always generate PO document
    exclude = ('category', 'sub_category', 'create_po', 'is_hq_order')
    
    def get_queryset(self, request):
        """Filter out HQ orders - only show site-specific POs"""
        qs = super().get_queryset(request)
        return qs.filter(is_hq_order=False)
    
    def get_changeform_initial_data(self, request):
        """Set up request in form context"""
        initial_data = super().get_changeform_initial_data(request)
        # Store request for use in form __init__
        self._current_request = request
        return initial_data
    
    def get_form(self, request, obj=None, **kwargs):
        """Intercept form creation to add request"""
        self._current_request = request
        form_class = super().get_form(request, obj, **kwargs)
        
        # Create a wrapper that passes request to __init__
        original_form_init = form_class.__init__
        
        def new_init(form_self, *args, **kw):
            kw['request'] = request
            original_form_init(form_self, *args, **kw)
        
        form_class.__init__ = new_init
        return form_class
    
    def order_date_display(self, obj):
        return obj.order_date.strftime('%d-%m-%Y') if obj.order_date else '-'
    order_date_display.short_description = "Order Date"
    order_date_display.admin_order_field = 'order_date'
    
    def due_date_display(self, obj):
        return obj.due_date.strftime('%d-%m-%Y') if obj.due_date else '-'
    due_date_display.short_description = "Due Date"
    due_date_display.admin_order_field = 'due_date'
    
    def total_display(self, obj):
        return obj.total_amount_display
    total_display.short_description = "Total"
    
    def _eye_icon(self, enabled, url=None):
        if enabled and url:
            return format_html(
                '<a href="{}" target="_blank" title="Preview PO as PDF" '
                'style="display: inline-block; padding: 6px 12px; background: #417690; color: white; '
                'border-radius: 4px; text-decoration: none; font-size: 13px;">'
                '<i class="fa fa-eye" style="margin-right: 5px;"></i>Preview PDF</a>',
                url,
            )
        return mark_safe(
            '<span style="display: inline-block; padding: 6px 12px; background: #ddd; color: #999; '
            'border-radius: 4px; font-size: 13px;" title="Save first to enable">'
            '<i class="fa fa-eye-slash" style="margin-right: 5px;"></i>Preview PDF</span>'
        )
    
    def _email_icon(self, enabled, url=None):
        if enabled and url:
            return format_html(
                '<a href="{}" target="_blank" title="Email PO to supplier" '
                'style="display: inline-block; padding: 6px 12px; background: #28a745; color: white; '
                'border-radius: 4px; text-decoration: none; font-size: 13px; margin-left: 10px;">'
                '<i class="fa fa-envelope" style="margin-right: 5px;"></i>Email PO</a>',
                url,
            )
        return mark_safe(
            '<span style="display: inline-block; padding: 6px 12px; background: #ddd; color: #999; '
            'border-radius: 4px; font-size: 13px; margin-left: 10px;" title="Save first to enable">'
            '<i class="fa fa-envelope" style="margin-right: 5px;"></i>Email PO</span>'
        )
    
    @admin.display(description="Preview")
    def view_po(self, obj):
        if not obj or not obj.pk:
            return self._eye_icon(False)
        url = reverse("inventory:po_document_preview", args=[obj.pk])
        return self._eye_icon(True, url)
    
    @admin.display(description="Email")
    def email_po(self, obj):
        if not obj or not obj.pk:
            return self._email_icon(False)
        url = reverse("inventory:email_po_document", args=[obj.pk])
        return self._email_icon(True, url)
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'get-stock-item-price/',
                self.admin_site.admin_view(self.get_stock_item_price_view),
                name='get_stock_item_price',
            ),
            path(
                'get-suppliers-by-subcategory/',
                self.admin_site.admin_view(self.get_suppliers_by_subcategory_view),
                name='get_suppliers_by_subcategory',
            ),
            path(
                'get-suppliers-by-category/',
                self.admin_site.admin_view(self.get_suppliers_by_category_view),
                name='get_suppliers_by_category',
            ),
        ]
        return custom_urls + urls
    
    def get_stock_item_price_view(self, request):
        """AJAX endpoint to get the stock item's standard price (Price Excluding VAT and Transport)"""
        from django.http import JsonResponse
        
        stock_item_id = request.GET.get('stock_item_id')
        if not stock_item_id:
            return JsonResponse({'price': 0, 'error': 'No stock item ID provided'})
        
        try:
            # Get stock item - filter by current site for security
            current_site = getattr(request, 'current_site', None)
            queryset = StockItem.objects.all()
            if current_site:
                queryset = queryset.filter(site=current_site)
            
            stock_item = queryset.get(pk=stock_item_id)
            
            # Return the stock item's own standard price (Price Excluding VAT and Transport)
            price = stock_item.standard_cost_excl_transport or 0
            
            return JsonResponse({
                'price': float(price),
                'unit': str(stock_item.unit_of_measure) if stock_item.unit_of_measure else '-'
            })
        except StockItem.DoesNotExist:
            return JsonResponse({'price': 0, 'error': 'Stock item not found'})
    
    def get_suppliers_by_subcategory_view(self, request):
        """AJAX endpoint to get suppliers filtered by sub_category"""
        from django.http import JsonResponse
        
        sub_category_id = request.GET.get('sub_category_id')
        if not sub_category_id:
            return JsonResponse({'suppliers': []})
        
        suppliers = Supplier.objects.filter(
            sub_category_id=sub_category_id,
            is_archived=False
        ).values('id', 'name').order_by('name')
        
        return JsonResponse({'suppliers': list(suppliers)})
    
    def get_suppliers_by_category_view(self, request):
        """AJAX endpoint to get suppliers filtered by category"""
        from django.http import JsonResponse
        
        category_id = request.GET.get('category_id')
        if not category_id:
            return JsonResponse({'suppliers': []})
        
        suppliers = Supplier.objects.filter(
            category_id=category_id,
            is_archived=False
        ).values('id', 'name').order_by('name')
        
        return JsonResponse({'suppliers': list(suppliers)})
    
    class Media:
        css = {
            'all': ('css/po_admin.css',)
        }
        js = (
            'js/po_currency_switch.js',
            'js/po_inline_move.js',
        )

