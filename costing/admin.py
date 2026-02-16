import json
from django.db.models import Sum
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html, mark_safe, format_html_join
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import path
from django.http import HttpResponse
from django.utils.safestring import mark_safe
from django.contrib import messages
from decimal import Decimal
from inventory.models import StockTransaction, StockItem
from manufacturing.models import Batch, Waste
from . import views
from django import forms
from .models import (
    BatchCosting, 
    OverheadItem, 
    SalaryCosting,
    OverheadCosting,
    SalaryPosition,
    ProductCosting,
    ProductCostingStockItem,
    BatchPriceApproval,
    BillingDocumentHeader,
    InvestorLoanCosting,
    InvestorLoanItem,
)
from transport.models import DeliverySite
from .forms import (
    SalaryPositionForm,
    OverheadItemForm,
    SalaryCostingForm,
    OverheadCostingForm,
    InvestorLoanCostingForm,
    InvestorLoanItemForm,
)
from commercial.models import CompanyDetails
from foodlinecontrol.admin_base import ArchivableAdmin
from tenants.admin_utils import SiteAwareModelAdmin


DATE_INPUTS_BILLING = ["%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"]

def get_company_currency():
    # Note: Admin list views don't have direct site context; default to HQ company (site=NULL)
    # In ModelAdmin methods with request context, use: CompanyDetails.objects.filter(site=request.current_site, is_active=True).first()
    company = CompanyDetails.objects.filter(site__isnull=True, is_active=True).first()
    if company and company.currency:
        return company.currency
    return "R"
    
class OverheadItemInline(admin.TabularInline):
    model = OverheadItem
    form = OverheadItemForm
    extra = 0
    ordering = ['item_type', 'item_name']
    fields = [
        'item_name', 'item_type', 'per_month',
        'per_week_display', 'per_day_display',
        'per_hour_display', 'per_unit_display', 'percentage_column',
    ]
    readonly_fields = [
        'per_week_display',
        'per_day_display',
        'per_hour_display',
        'per_unit_display',
        'percentage_column',
    ]

    def per_week_display(self, obj):
        if not obj.id:
            return "-"
        cur = get_company_currency()
        value = f"{cur} {float(obj.per_week):,.2f}"
        return format_html('<span style="float:right;">{}</span>', value)

    def per_day_display(self, obj):
        if not obj.id:
            return "-"
        cur = get_company_currency()
        value = f"{cur} {float(obj.per_day):,.2f}"
        return format_html('<span style="float:right;">{}</span>', value)

    def per_hour_display(self, obj):
        if not obj.id:
            return "-"
        cur = get_company_currency()
        value = f"{cur} {float(obj.per_hour):,.2f}"
        return format_html('<span style="float:right;">{}</span>', value)

    def per_unit_display(self, obj):
        if not obj.id:
            return "-"
        cur = get_company_currency()
        value = f"{cur} {float(obj.per_unit):,.4f}"
        return format_html('<span style="float:right;">{}</span>', value)

    def percentage_column(self, obj):
        if not obj.id:
            return "-"
        value = "{:.2f}%".format(float(obj.percentage))
        return format_html('<span style="display:block; text-align:center;">{}</span>', value)
    percentage_column.short_description = "% Total"

@admin.register(OverheadCosting)
class OverheadCostingAdmin(SiteAwareModelAdmin, ArchivableAdmin): 
    form = OverheadCostingForm
    inlines = [OverheadItemInline]
    search_fields = ['description']
    
    class Media:
        js = ('js/overhead_dynamic_calc.js',)
    
    def get_queryset(self, request):
        """Prefetch related items for efficient calculation of totals"""
        qs = super().get_queryset(request)
        return qs.prefetch_related('items')

    def fixed_subtotal_display(self, obj):
        cur = get_company_currency()
        value = float(obj.fixed_subtotal) if obj.fixed_subtotal else 0.0
        formatted = f"{cur} {value:,.2f}"
        return format_html('<span id="overhead-fixed-total">{}</span>', formatted)
    fixed_subtotal_display.short_description = "Fixed"

    def variable_subtotal_display(self, obj):
        cur = get_company_currency()
        value = float(obj.variable_subtotal) if obj.variable_subtotal else 0.0
        formatted = f"{cur} {value:,.2f}"
        return format_html('<span id="overhead-variable-total">{}</span>', formatted)
    variable_subtotal_display.short_description = "Variable"

    def grand_total_display(self, obj):
        cur = get_company_currency()
        value = float(obj.grand_total) if obj.grand_total else 0.0
        color = "darkred" if value > 100000 else "black"
        formatted = f"{cur} {value:,.2f}"
        return format_html('<span id="overhead-grand-total" style="color:{};">{}</span>', color, formatted)
    grand_total_display.short_description = "Grand Total"

    def price_per_unit_display(self, obj):
        cur = get_company_currency()
        value = float(obj.price_per_unit) if obj.price_per_unit else 0.0
        formatted = f"{cur} {value:,.2f}" if value > 0 else "-"
        return format_html('<span id="overhead-price-per-unit">{}</span>', formatted)
    price_per_unit_display.short_description = "Price per Unit"
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == 'production_units':
            formfield.widget.attrs['style'] = 'text-align:right; padding-right:4px;'
        return formfield

    readonly_fields = [
        'fixed_subtotal_display',
        'variable_subtotal_display',
        'grand_total_display',
        'price_per_unit_display'
    ]
    
    list_display = [
        'description', 
        'date', 
        'use_as_default', 
        'fixed_subtotal_display',
        'variable_subtotal_display',
        'grand_total_display', 
        'price_per_unit_display', 
        'production_units'
    ]
    list_display_links = ['description']
    list_filter = ['date']
    search_fields = ['description']
    
    fieldsets = (
        ('Header Information', {'fields': (('date', 'description', 'production_units', 'use_as_default'),)}),
        ('Totals', {'fields': (('fixed_subtotal_display', 'variable_subtotal_display', 'grand_total_display', 'price_per_unit_display'),)}),
    )


class InvestorLoanItemInline(admin.TabularInline):
    model = InvestorLoanItem
    form = InvestorLoanItemForm
    extra = 0
    ordering = ['item_type', 'item_name']
    fields = [
        'item_name', 'item_type', 'total_amount', 'monthly_payment',
        'per_unit_display', 'percentage_column',
    ]
    readonly_fields = [
        'per_unit_display',
        'percentage_column',
    ]

    def per_unit_display(self, obj):
        if not obj.id:
            return "-"
        cur = get_company_currency()
        value = f"{cur} {float(obj.per_unit):,.4f}"
        return format_html('<span style="float:right;">{}</span>', value)
    per_unit_display.short_description = "Per Unit"

    def percentage_column(self, obj):
        if not obj.id:
            return "-"
        value = "{:.2f}%".format(float(obj.percentage))
        return format_html('<span style="display:block; text-align:center;">{}</span>', value)
    percentage_column.short_description = "% Total"


@admin.register(InvestorLoanCosting)
class InvestorLoanCostingAdmin(SiteAwareModelAdmin, ArchivableAdmin): 
    form = InvestorLoanCostingForm
    inlines = [InvestorLoanItemInline]
    search_fields = ['description']
    
    def get_queryset(self, request):
        """Prefetch related items for efficient calculation of totals"""
        qs = super().get_queryset(request)
        return qs.prefetch_related('items')

    def investment_subtotal_display(self, obj):
        cur = get_company_currency()
        value = float(obj.investment_subtotal) if obj.investment_subtotal else 0.0
        formatted = f"{cur} {value:,.2f}"
        return format_html('<span id="investor-loan-investment-total">{}</span>', formatted)
    investment_subtotal_display.short_description = "Investment"

    def loan_subtotal_display(self, obj):
        cur = get_company_currency()
        value = float(obj.loan_subtotal) if obj.loan_subtotal else 0.0
        formatted = f"{cur} {value:,.2f}"
        return format_html('<span id="investor-loan-loan-total">{}</span>', formatted)
    loan_subtotal_display.short_description = "Loan"

    def grand_total_display(self, obj):
        cur = get_company_currency()
        value = float(obj.grand_total) if obj.grand_total else 0.0
        color = "darkred" if value > 100000 else "black"
        formatted = f"{cur} {value:,.2f}"
        return format_html('<span id="investor-loan-grand-total" style="color:{};">{}</span>', color, formatted)
    grand_total_display.short_description = "Grand Total"

    def price_per_unit_display(self, obj):
        cur = get_company_currency()
        value = float(obj.price_per_unit) if obj.price_per_unit else 0.0
        formatted = f"{cur} {value:,.2f}" if value > 0 else "-"
        return format_html('<span id="investor-loan-price-per-unit">{}</span>', formatted)
    price_per_unit_display.short_description = "Price per Unit"
    
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == 'production_units':
            formfield.widget.attrs['style'] = 'text-align:right; padding-right:4px;'
        return formfield

    readonly_fields = [
        'investment_subtotal_display',
        'loan_subtotal_display',
        'grand_total_display',
        'price_per_unit_display'
    ]
    
    list_display = [
        'description', 
        'date', 
        'use_as_default', 
        'investment_subtotal_display',
        'loan_subtotal_display',
        'grand_total_display', 
        'price_per_unit_display', 
        'production_units'
    ]
    list_display_links = ['description']
    list_filter = ['date']
    search_fields = ['description']
    
    fieldsets = (
        ('Header Information', {'fields': (('date', 'description', 'production_units', 'use_as_default'),)}),
        ('Totals', {'fields': (('investment_subtotal_display', 'loan_subtotal_display', 'grand_total_display', 'price_per_unit_display'),)}),
    )


class SalaryPositionInline(admin.TabularInline):
    model = SalaryPosition
    form = SalaryPositionForm
    extra = 0
    ordering = ['position_name']
    fields = [
        'position_name', 'general_workers', 'rate_per_hour',
        'qa_workers', 'qa_rate_per_hour', 'shifts', 'shift_hours',
        'total_per_hour_display',
        'days_worked',
        'total_per_month_display',
        'percentage_display',
    ]
    readonly_fields = ['total_per_hour_display', 'total_per_month_display', 'percentage_display']
    
    def total_per_hour_display(self, obj):
        if not obj.id:
            return "-"
        cur = get_company_currency()
        value = f"{cur} {float(obj.total_per_hour):,.2f}"
        return value
    total_per_hour_display.short_description = "Per Hour"
    
    def total_per_month_display(self, obj):
        if not obj.id:
            return "-"
        cur = get_company_currency()
        value = f"{cur} {float(obj.total_per_month):,.2f}"
        return value
    total_per_month_display.short_description = "Total for Month"
    
    def percentage_display(self, obj):
        if not obj.id:
            return "-"
        return f"{float(obj.percentage):.2f}%"
    percentage_display.short_description = "% Total"

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        numeric_center = 'text-align:center;'
        numeric_right = 'text-align:right; padding-right:4px;'
        if db_field.name in ['general_workers', 'qa_workers', 'shifts', 'shift_hours']:
            formfield.widget.attrs['style'] = 'width:60px; ' + numeric_center
        elif db_field.name in ['rate_per_hour', 'qa_rate_per_hour', 'days_worked']:
            formfield.widget.attrs['style'] = 'width:60px; ' + numeric_right
        elif db_field.name == 'position_name':
            formfield.widget.attrs['style'] = 'width:170px;'
        return formfield

@admin.register(SalaryCosting)
class SalaryCostingAdmin(SiteAwareModelAdmin, ArchivableAdmin): 
    form = SalaryCostingForm
    
    search_fields = ['description']

    class Media:
        js = (
            'js/hide_today.js',
            'js/salary_dynamic_calc.js',
        )

    inlines = [SalaryPositionInline]
    
    def get_queryset(self, request):
        """Prefetch related positions for efficient calculation of totals"""
        qs = super().get_queryset(request)
        return qs.prefetch_related('positions')

    def fixed_subtotal_display(self, obj):
        cur = get_company_currency()
        value = float(obj.fixed_subtotal or 0)
        formatted = f"{cur} {value:,.2f}"
        return format_html('<div style="text-align:center;"><span id="salary-fixed-total">{}</span></div>', formatted)
    fixed_subtotal_display.short_description = "Fixed subtotal"

    def production_subtotal_display(self, obj):
        cur = get_company_currency()
        value = float(obj.production_subtotal or 0)
        formatted = f"{cur} {value:,.2f}"
        return format_html('<div style="text-align:center;"><span id="salary-production-total">{}</span></div>', formatted)
    production_subtotal_display.short_description = "Production subtotal"

    def grand_total_display(self, obj):
        cur = get_company_currency()
        value = float(obj.grand_total or 0)
        color = "darkred" if value > 100000 else "black"
        formatted = f"{cur} {value:,.2f}"
        return format_html('<div style="text-align:center;"><span id="salary-grand-total" style="color:{};">{}</span></div>', color, formatted)
    grand_total_display.short_description = "Grand Total"

    def price_per_unit_display(self, obj):
        cur = get_company_currency()
        
        value = float(obj.price_per_unit or 0)
        formatted = f"{cur} {value:,.2f}" if value > 0 else "-"
        
        html = f'<div style="text-align:center;"><span id="salary-price-per-unit">{formatted}</span>'
        html += '<br><small style="color:#666; font-style:italic;">Grand total / Units + Bonus</small>'
        html += '</div>'
        
        return mark_safe(html)
    price_per_unit_display.short_description = "Price per Unit"
    def management_salary_display(self, obj):
        cur = get_company_currency()
        value = float(obj.management_salary or 0)
        return f"{cur} {value:,.2f}"
    management_salary_display.short_description = "Management"

    def office_salary_display(self, obj):
        cur = get_company_currency()
        value = float(obj.office_salary or 0)
        return f"{cur} {value:,.2f}"
    office_salary_display.short_description = "Office"

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name in ['management_salary', 'office_salary', 'production_units']:
            formfield.widget.attrs['style'] = 'text-align:right; padding-right:4px;'
        elif db_field.name in ['percentage_bonus', 'production_months']:
            formfield.widget.attrs['style'] = 'text-align:right; padding-right:4px; width:80px;'
        return formfield
        
    readonly_fields = [
        'fixed_subtotal_display',
        'production_subtotal_display',
        'grand_total_display',
        'price_per_unit_display',
    ]

    list_display = [
        'description',
        'date',
        'use_as_default',
        'management_salary_display',
        'office_salary_display',
        'fixed_subtotal_display',
        'production_subtotal_display',
        'grand_total_display',
        'price_per_unit_display',
        'production_units',
    ]
    list_display_links = ['description']
    list_filter = ['date']
    search_fields = ['description']

    fieldsets = (
        ('Header Information', {
            'fields': (('date', 'description', 'production_units', 'use_as_default'),)
        }),
        ('Fixed Salaries', {
            'fields': (('management_salary', 'office_salary', 'fixed_subtotal_display', 'grand_total_display'),)
        }),
        ('Totals', {
            'fields': (('production_subtotal_display', 'percentage_bonus', 'production_months', 'price_per_unit_display'),)
        }),
    )
    
class BatchPriceApprovalInline(admin.TabularInline):
    """Inline editor for batch prices"""
    model = BatchPriceApproval
    extra = 0
    fields = ('batch', 'batch_price_per_unit', 'is_approved')
    readonly_fields = ('batch',)
    can_delete = False
    fk_name = 'batch_costing'
    
    def get_queryset(self, request):
        """Ensure we always show existing records"""
        qs = super().get_queryset(request)
        return qs.select_related('batch')
    
    def has_add_permission(self, request, obj=None):
        """Don't allow adding via inline - created by signal"""
        return False

@admin.register(BatchCosting)
class BatchCostingAdmin(SiteAwareModelAdmin, ArchivableAdmin):
    """BatchCosting - Auto-populated from Production system"""
    
    class Media:
        js = (
            'js/batch_costing_defaults.js',
            'js/batch_costing_summary.js',
            'js/batch_costing.js',
            'js/batch_price_approval_save.js',
            'js/admin_enter_fix.js',
        )
        css = {
            'all': (
                'css/product_costing.css',
            )
        }
        
    fieldsets = (
        ('Production Information', {
            'fields': (
                'production_date_display', # Use read-only display method
            ),
        }),
        ('Summary Items', {
            'fields': ('summary_items_display',),
            'classes': ('grp-collapse', 'grp-open'), 
        }),
        ('Costing Records', {
            'fields': (
                ('stock_item_price_use',),
                ('overhead_costing', 'overhead_price_per_unit_display'),
                ('salary_costing', 'salary_price_per_unit_display'),
                ('investor_loan_costing', 'investor_loan_price_per_unit_display'),
                ('use_markup', 'markup_percentage'),
                ('use_markup_per_unit', 'markup_per_unit'),
                ('price'),
            )
        }),
        ('Batch Pricing & Approval', {
            'fields': ('batch_approvals_display',),
            'classes': ('wide',),
            'description': '🏷️ Set prices and approval status for each batch'
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )

    # READ-ONLY fields
    readonly_fields = [
        'production_date_display',
        'overhead_price_per_unit_display', 
        'salary_price_per_unit_display',
        'investor_loan_price_per_unit_display',
        'stock_item_price_display', 
        'summary_items_display',
        'costing_summary_display',
        'batch_approvals_display',
        'total_cost_per_unit_display',
        'pricedisplay',
    ]

    list_display = [
        'production_date_display',
        'batch_prices_full_table_display',
    ]
    
    search_fields = [
        'production_date__batches__batch_number',  # Search by batch number
        'production_date__production_date',        # Search by production date
    ]
    
    list_filter = ['date_created', 'production_date']

    ordering = ('-date_created',)
    
    # ============= BATCH APPROVALS DISPLAY =============
    
    def production_date_display(self, obj):
        if obj.batch and getattr(obj.batch, "production_date", None):
            date_str = obj.batch.production_date.strftime("%d/%m/%y")
            url = reverse(
                'admin:inventory_finishedproducttransaction_change',
                args=[obj.pk]
            )
            return format_html(
                '<a href="{}" style="display: block; text-align: center; text-decoration: none; color: #417690;">{}</a>',
                url,
                date_str,
            )
        return mark_safe('<div style="text-align: center;">-</div>')

    production_date_display.short_description = "Production Date"
    production_date_display.admin_order_field = 'batch__production_date'
     
    def get_search_results(self, request, queryset, search_term):
        """Custom search: batch number + flexible date formats"""
        from datetime import datetime
        
        # Try normal search first (batch numbers)
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        
        if search_term:
            # Try parsing as dd/mm/yyyy or dd-mm-yyyy
            date_formats = ['%d/%m/%Y', '%d-%m-%Y', '%d/%m/%y', '%d-%m-%y']
            
            for fmt in date_formats:
                try:
                    parsed_date = datetime.strptime(search_term.strip(), fmt).date()
                    
                    # Search for that exact date
                    date_qs = self.model.objects.filter(
                        production_date__production_date=parsed_date
                    )
                    
                    queryset = queryset | date_qs
                    use_distinct = True
                    break
                except ValueError:
                    continue
        
        return queryset, use_distinct


        
    def batch_approvals_display(self, obj):
        """Display batch approvals with all batch details, including Ready for Dispatch"""
        if not obj or not obj.pk:
            return "Save BatchCosting first"

        approvals = obj.price_approvals.all().order_by('batch__batch_number')
        if not approvals:
            return "No batch approvals found"

        # Try get Waste record for this production date
        waste = None
        if obj.production_date:
            try:
                prod_date = obj.production_date.production_date
                waste = Waste.objects.filter(production_date=prod_date).first()
            except Exception:
                pass

        rows = []
        for approval in approvals:
            batch = approval.batch
            product_name = str(batch.product) if batch.product else "N/A"

            shift_total = float(batch.shift_total or 0)

            # Defaults
            nsi_qty = 0.0
            retention_qty = 0.0
            unclear_qty = 0.0

            # Pull per‑batch waste from JSON/dict fields if Waste record exists
            if waste:
                try:
                    key = batch.batch_number
                    if waste.nsi_sample_per_batch and isinstance(waste.nsi_sample_per_batch, dict):
                        nsi_qty = float(waste.nsi_sample_per_batch.get(key, 0) or 0)
                    if waste.retention_sample_per_batch and isinstance(waste.retention_sample_per_batch, dict):
                        retention_qty = float(waste.retention_sample_per_batch.get(key, 0) or 0)
                    if waste.unclear_coding_per_batch and isinstance(waste.unclear_coding_per_batch, dict):
                        unclear_qty = float(waste.unclear_coding_per_batch.get(key, 0) or 0)
                except Exception:
                    pass

            ready_for_dispatch = max(0, shift_total - nsi_qty - retention_qty - unclear_qty)

            rows.append(f"""
                <tr>
                    <td style="border: 1px solid #ddd; padding: 10px; text-align: center; width: 120px;">
                        <strong>{batch.batch_number}</strong>
                    </td>
                    <td style="border: 1px solid #ddd; padding: 10px; width: 250px;">
                        {product_name}
                    </td>
                    <td style="border: 1px solid #ddd; padding: 10px; text-align: center; width: 80px;">
                        {batch.size}
                    </td>
                    <td style="border: 1px solid #ddd; padding: 10px; text-align: center; width: 80px;">
                        <strong>{batch.shift_total:,}</strong>
                    </td>
                    <td style="border: 1px solid #ddd; padding: 10px; text-align: center; width: 150px;">
                        <span style="background-color: #e3f2fd; padding: 3px 8px; border-radius: 3px; font-size: 12px;">
                            {batch.get_formatted_status()}
                        </span>
                    </td>
                    <td style="border: 1px solid #ddd; padding: 10px; text-align: center; font-weight: bold; color: #d32f2f; width: 120px;">
                        {ready_for_dispatch:,.0f}
                    </td>
                    <td style="border: 1px solid #ddd; padding: 10px; text-align: right; width: 150px;">
                        <input type="text" value="{float(approval.batch_price_per_unit or 0):.2f}"
                               data-approval-id="{approval.id}" class="batch-price-input"
                               style="width: 100%; padding: 5px; text-align: right;">
                    </td>
                    <td style="border: 1px solid #ddd; padding: 10px; text-align: center; width: 80px;">
                        <input type="checkbox" data-approval-id="{approval.id}" class="batch-approval-checkbox"
                               {'checked' if approval.is_approved else ''}>
                    </td>
                </tr>
            """)


        html = f"""
            <table style="width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 10px; table-layout: fixed;">
                <thead>
                    <tr style="background-color: #1976d2; color: white;">
                        <th style="border: 1px solid #ddd; padding: 10px; width: 120px; text-align: center;">Batch Code</th>
                        <th style="border: 1px solid #ddd; padding: 10px; width: 250px; text-align: center;">Product</th>
                        <th style="border: 1px solid #ddd; padding: 10px; width: 80px; text-align: center;">Size</th>
                        <th style="border: 1px solid #ddd; padding: 10px; width: 80px; text-align: center;">Units</th>
                        <th style="border: 1px solid #ddd; padding: 10px; width: 150px; text-align: center;">Status</th>
                        <th style="border: 1px solid #ddd; padding: 10px; width: 120px; text-align: center;">Ready Dispatch</th>
                        <th style="border: 1px solid #ddd; padding: 10px; width: 150px; text-align: center;">Price per Unit</th>
                        <th style="border: 1px solid #ddd; padding: 10px; width: 80px; text-align: center;">Approved</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(rows)}
                </tbody>
            </table>
        """

        return mark_safe(html)

    batch_approvals_display.short_description = ""

    def get_company_currency():
        company = CompanyDetails.objects.filter(site__isnull=True, is_active=True).first()
        if company and company.currency:
            return company.currency
        return "R"

    def batch_prices_full_table_display(self, obj):
        """
        Display COMPLETE batch pricing table in LIST VIEW - reads from DB.
        Compact version of the Batch Pricing & Approvals table.
        """
        if not obj.pk:
            return "-"

        approvals = BatchPriceApproval.objects.filter(
            batch_costing=obj
        ).select_related('batch', 'batch__product').order_by('batch__batch_number')

        if not approvals.exists():
            return mark_safe(
                '<span style="color: #999; font-size: 12px;">No batch prices set</span>'
            )

        # currency for this table
        cur = get_company_currency()

        # Try get Waste data for Ready Dispatch
        try:
            production_date_field = obj.production_date.production_date
            waste = Waste.objects.filter(production_date=production_date_field).first()
        except Exception:
            waste = None

        rows = []
        for approval in approvals:
            batch = approval.batch
            product_name = str(batch.product) if batch.product else 'N/A'
            price = float(approval.batch_price_per_unit or 0)

            shift_total = float(batch.shift_total or 0)
            nsi_qty = 0
            retention_qty = 0
            unclear_qty = 0

            if waste:
                try:
                    key = batch.batch_number
                    if waste.nsi_sample_per_batch and isinstance(waste.nsi_sample_per_batch, dict):
                        nsi_qty = float(waste.nsi_sample_per_batch.get(key, 0) or 0)
                    if waste.retention_sample_per_batch and isinstance(waste.retention_sample_per_batch, dict):
                        retention_qty = float(waste.retention_sample_per_batch.get(key, 0) or 0)
                    if waste.unclear_coding_per_batch and isinstance(waste.unclear_coding_per_batch, dict):
                        unclear_qty = float(waste.unclear_coding_per_batch.get(key, 0) or 0)
                except Exception:
                    pass

            ready_for_dispatch = max(0, shift_total - nsi_qty - retention_qty - unclear_qty)

            approved_icon = '✓' if approval.is_approved else '✗'
            approved_color = 'green' if approval.is_approved else 'orange'

            batch_status = batch.get_formatted_status()

            rows.append(f"""
                <tr style="border-bottom: 1px solid #ddd; font-size: 11px;">
                    <td style="padding: 4px 6px; font-weight: bold; white-space: nowrap;">
                        {batch.batch_number}
                    </td>
                    <td style="padding: 4px 6px; max-width: 200px; overflow: hidden; text-overflow: ellipsis;">
                        {product_name}
                    </td>
                    <td style="padding: 4px 6px; text-align: center; white-space: nowrap;">
                        {batch.size or 'N/A'}
                    </td>
                    <td style="padding: 4px 6px; text-align: right; white-space: nowrap;">
                        {batch.shift_total:,}
                    </td>
                    <td style="padding: 4px 6px; text-align: center;">
                        <span style="background-color: #e3f2fd; color: #1976d2; padding: 1px 4px; border-radius: 3px; font-size: 10px; white-space: nowrap;">
                            {batch_status}
                        </span>
                    </td>
                    <td style="padding: 4px 6px; text-align: right; white-space: nowrap; font-weight: bold; color: #0277bd;">
                        {ready_for_dispatch:,.0f}
                    </td>
                    <td style="padding: 4px 6px; text-align: right; white-space: nowrap; font-weight: bold;">
                        {cur} {price:,.2f}
                    </td>
                    <td style="padding: 4px 6px; text-align: center; color: {approved_color}; font-weight: bold;">
                        {approved_icon}
                    </td>
                </tr>
            """)

        html = f"""
        <div style="margin-bottom: 5px;">
            <table style="width: 100%; border-collapse: collapse; font-size: 11px; background: white; border: 1px solid #ddd;">
                <thead>
                    <tr style="background-color: #1976d2; color: white; font-weight: bold;">
                        <th style="padding: 4px 6px; text-align: left;  width: 100px;">Batch</th>
                        <th style="padding: 4px 6px; text-align: left;  width: 220px;">Product</th>
                        <th style="padding: 4px 6px; text-align: center; width: 70px;">Size</th>
                        <th style="padding: 4px 6px; text-align: right;  width: 80px;">Units</th>
                        <th style="padding: 4px 6px; text-align: center; width: 130px;">Status</th>
                        <th style="padding: 4px 6px; text-align: right;  width: 110px;">Ready Dispatch</th>
                        <th style="padding: 4px 6px; text-align: right;  width: 110px;">Price/Unit</th>
                        <th style="padding: 4px 6px; text-align: center; width: 70px;">Approved</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(rows)}
                </tbody>
            </table>
        </div>
        """

        return mark_safe(html)

    batch_prices_full_table_display.short_description = "Batch Pricing & Approvals"

    # ============= PRICING DISPLAYS =============
    def pricedisplay(self, obj):
        if not obj:
            return "-"
        cur = getcompanycurrency()
        value = float(obj.price or 0)
        return format_html("<strong>{:,.2f}</strong> {}", value, cur)
    pricedisplay.short_description = "Selling Price"

    def overhead_price_per_unit_display(self, obj):
        """Display overhead price per unit - uses snapshot if available"""
        if not obj:
            return "-"
        cur = get_company_currency()
        # Use the model's property which handles snapshot logic
        value = obj.overhead_price_per_unit
        if value == 0 and not obj.overhead_costing:
            return "-"
        return f"{cur} {float(value):,.2f}"
    overhead_price_per_unit_display.short_description = "Price per Unit"

    def salary_price_per_unit_display(self, obj):
        """Display salary price per unit - uses snapshot if available"""
        if not obj:
            return "-"
        cur = get_company_currency()
        # Use the model's property which handles snapshot logic
        value = obj.salary_price_per_unit
        if value == 0 and not obj.salary_costing:
            return "-"
        return f"{cur} {float(value):,.2f}"
    salary_price_per_unit_display.short_description = "Price per Unit"

    def investor_loan_price_per_unit_display(self, obj):
        """Display investor/loan price per unit - uses snapshot if available"""
        if not obj:
            return "-"
        cur = get_company_currency()
        # Use the model's property which handles snapshot logic
        value = obj.investor_loan_price_per_unit
        if value == 0 and not obj.investor_loan_costing:
            return "-"
        return f"{cur} {float(value):,.2f}"
    investor_loan_price_per_unit_display.short_description = "Price per Unit"

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter overhead_costing, salary_costing, and investor_loan_costing by current site"""
        current_site = getattr(request, 'current_site', None)
        
        if db_field.name == "overhead_costing":
            if current_site:
                # Site admin: show ONLY overhead costings for this site
                kwargs["queryset"] = OverheadCosting.objects.filter(site_id=current_site.id)
            else:
                # HQ context: show all overhead costings
                kwargs["queryset"] = OverheadCosting.objects.all()
        
        elif db_field.name == "salary_costing":
            if current_site:
                # Site admin: show ONLY salary costings for this site
                kwargs["queryset"] = SalaryCosting.objects.filter(site_id=current_site.id)
            else:
                # HQ context: show all salary costings
                kwargs["queryset"] = SalaryCosting.objects.all()
        
        elif db_field.name == "investor_loan_costing":
            if current_site:
                # Site admin: show ONLY investor/loan costings for this site
                kwargs["queryset"] = InvestorLoanCosting.objects.filter(site_id=current_site.id)
            else:
                # HQ context: show all investor/loan costings
                kwargs["queryset"] = InvestorLoanCosting.objects.all()
        
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def stock_item_price_display(self, obj):
        if not obj:
            return "-"
        cur = get_company_currency()
        price = float(obj.stock_item_price_use or 0)
        return format_html('<strong>{} {:,.2f}</strong>', cur, price)
    stock_item_price_display.short_description = "Stock Item Price"

    def costing_summary_display(self, obj):
        if not obj:
            return "No data"
        cur = get_company_currency()
        inv = float(obj.cost_per_unit_inventory or 0)
        oh = float(obj.overhead_price_per_unit or 0)
        sal = float(obj.salary_price_per_unit or 0)
        il = float(obj.investor_loan_price_per_unit or 0)
        total = float(obj.total_cost_per_unit or 0)
        units = obj.total_shift_total or 0
        prod_cost = float(obj.total_production_cost or 0)

        html = f"""<div style="background-color: #f3e5f5; padding: 20px; border-radius: 5px; border-left: 4px solid #7b1fa2;">
            <h4 style="margin-top: 0; color: #7b1fa2;">Cost Per Unit Breakdown</h4>
            <table style="width: 100%; font-size: 14px; margin-bottom: 15px;">
                <tr><td style="padding: 8px;"><strong>Inventory Cost/Unit:</strong></td>
                    <td style="padding: 8px; text-align: right;">{cur} {inv:,.4f}</td></tr>
                <tr><td style="padding: 8px;"><strong>Overhead Cost/Unit:</strong></td>
                    <td style="padding: 8px; text-align: right;">{cur} {oh:,.2f}</td></tr>
                <tr><td style="padding: 8px;"><strong>Salary Cost/Unit:</strong></td>
                    <td style="padding: 8px; text-align: right;">{cur} {sal:,.2f}</td></tr>
                <tr><td style="padding: 8px;"><strong>Investor/Loan Cost/Unit:</strong></td>
                    <td style="padding: 8px; text-align: right;">{cur} {il:,.2f}</td></tr>
                <tr style="background-color: #e1bee7; font-weight: bold; font-size: 15px;"><td style="padding: 10px;"><strong>TOTAL COST/UNIT:</strong></td>
                    <td style="padding: 10px; text-align: right;">{cur} {total:,.4f}</td></tr></table>
            <hr style="border: 1px solid #ddd; margin: 15px 0;">
            <h4 style="margin: 15px 0 10px 0; color: #7b1fa2;">Total Production Cost</h4>
            <table style="width: 100%; font-size: 14px;">
                <tr><td style="padding: 8px;"><strong>Total Units Produced:</strong></td>
                    <td style="padding: 8px; text-align: right;">{units:,}</td></tr>
                <tr style="background-color: #e1bee7; font-weight: bold; font-size: 15px;"><td style="padding: 10px;"><strong>TOTAL PRODUCTION COST:</strong></td>
                    <td style="padding: 10px; text-align: right;">{cur} {prod_cost:,.2f}</td></tr></table></div>"""
        return mark_safe(html)

    def summary_items_display(self, obj):
        """Display summary items table - populated via external JS from API"""
        if not obj or not obj.production_date:
            return "Select a production date first"
        
        # ✅ Inject production_date ID as data attribute for JavaScript
        production_id = obj.production_date.pk if obj.production_date else None
        
        html = f"""
        <div id="summary-items-container" 
             data-production-id="{production_id}"
             style="
            margin: 20px -500px 20px -500px; 
            padding: 0 350px;
            width: auto;
            max-width: none;
            overflow-x: auto;
        ">
            <p style="color: #999; font-style: italic;">Loading summary items...</p>
        </div>
        """
        
        return mark_safe(html)

    summary_items_display.short_description = ""


    # ============= LIST DISPLAY METHODS =============
    
    def total_cost_per_unit_display(self, obj):
        if not obj:
            return "-"
        cur = get_company_currency()
        value = float(obj.total_cost_per_unit or 0)
        return format_html(
            '<strong style="color: #d32f2f; font-size: 14px;">{} {:,.4f}</strong>',
            cur,
            value,
        )
    total_cost_per_unit_display.short_description = "Total Cost/Unit"

    def production_date_display(self, obj):
        if obj and obj.production_date:
            date_str = obj.production_date.production_date.strftime('%d/%m/%Y')
            return format_html('<div style="text-align: center;">{}</div>', date_str)
        return "-"
    production_date_display.short_description = "Date"

    # ============= PERMISSIONS =============
    
    def has_add_permission(self, request):
        """BatchCosting is auto-created by signal"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Allow deletion"""
        return True
    
    # ============= FORM CUSTOMIZATION =============
    
    def get_form(self, request, obj=None, **kwargs):
        """Customize form before rendering"""
        form = super().get_form(request, obj, **kwargs)
        
        # Make production_date read-only AND hide the add/change buttons
        if 'production_date' in form.base_fields:
            form.base_fields['production_date'].disabled = True
            widget = form.base_fields['production_date'].widget
            widget.can_add_related = False
            widget.can_change_related = False
            widget.can_delete_related = False
        
        return form
        
    def production_date_display(self, obj):
        if obj and obj.production_date:
            return obj.production_date.production_date.strftime('%d/%m/%Y')
        return "-"
    production_date_display.short_description = "Production Date"
    
    def change_view(self, request, object_id=None, form_url='', extra_context=None):
        """Ensure BatchPriceApproval records exist before rendering form"""
        extra_context = extra_context or {}
        
        # Pass company currency to template for JavaScript
        extra_context['company_currency'] = get_company_currency()
        
        if object_id:
            bc = BatchCosting.objects.get(pk=object_id)
            
            # If no approvals exist, create them NOW
            if not bc.price_approvals.exists() and bc.production_date:
                from manufacturing.models import Batch
                
                # Get the actual production date from the Production object
                prod_date = bc.production_date.production_date
                batches = Batch.objects.filter(production_date=prod_date)
                
                for batch in batches:
                    BatchPriceApproval.objects.get_or_create(
                        batch_costing=bc,
                        batch=batch,
                        defaults={
                            'batch_price_per_unit': 0,
                            'is_approved': False,
                        }
                    )
            
            # For existing records, pass original costing IDs and snapshot values for JS comparison
            extra_context['original_overhead_costing_id'] = bc.overhead_costing_id or ''
            extra_context['original_salary_costing_id'] = bc.salary_costing_id or ''
            extra_context['original_investor_loan_costing_id'] = bc.investor_loan_costing_id or ''
            extra_context['overhead_snapshot'] = float(bc.overhead_price_per_unit_snapshot or 0)
            extra_context['salary_snapshot'] = float(bc.salary_price_per_unit_snapshot or 0)
            extra_context['investor_loan_snapshot'] = float(bc.investor_loan_price_per_unit_snapshot or 0)
        
        response = super().change_view(request, object_id, form_url, extra_context)
        
        # Inject currency and original values as JavaScript global variables
        if hasattr(response, 'render'):
            response.render()
        
        currency = extra_context.get('company_currency', 'R')
        orig_overhead = extra_context.get('original_overhead_costing_id', '')
        orig_salary = extra_context.get('original_salary_costing_id', '')
        orig_investor_loan = extra_context.get('original_investor_loan_costing_id', '')
        overhead_snap = extra_context.get('overhead_snapshot', 0)
        salary_snap = extra_context.get('salary_snapshot', 0)
        investor_loan_snap = extra_context.get('investor_loan_snapshot', 0)
        
        script_tag = f'''<script>
            window.COMPANY_CURRENCY = "{currency}";
            window.ORIGINAL_OVERHEAD_COSTING_ID = "{orig_overhead}";
            window.ORIGINAL_SALARY_COSTING_ID = "{orig_salary}";
            window.ORIGINAL_INVESTOR_LOAN_COSTING_ID = "{orig_investor_loan}";
            window.OVERHEAD_SNAPSHOT = {overhead_snap};
            window.SALARY_SNAPSHOT = {salary_snap};
            window.INVESTOR_LOAN_SNAPSHOT = {investor_loan_snap};
        </script>'''.encode('utf-8')
        
        if hasattr(response, 'content'):
            response.content = response.content.replace(b'</head>', script_tag + b'</head>')
        
        return response

    def get_changeform_initial_data(self, request):
        """Pre-populate form initial data when adding/editing BatchCosting"""
        initial = super().get_changeform_initial_data(request)
        
        from .models import OverheadCosting, SalaryCosting, InvestorLoanCosting
        
        if 'overhead_costing' not in initial or initial.get('overhead_costing') is None:
            default_oh = OverheadCosting.get_default()
            if default_oh:
                initial['overhead_costing'] = default_oh.pk
        
        if 'salary_costing' not in initial or initial.get('salary_costing') is None:
            default_sal = SalaryCosting.get_default()
            if default_sal:
                initial['salary_costing'] = default_sal.pk
        
        if 'investor_loan_costing' not in initial or initial.get('investor_loan_costing') is None:
            default_il = InvestorLoanCosting.get_default()
            if default_il:
                initial['investor_loan_costing'] = default_il.pk
        
        return initial


class ProductCostingStockItemInline(admin.TabularInline):
    model = ProductCostingStockItem
    extra = 0
    fields = (
        'stock_item',
        'usage_per_unit',
        'unit_of_measure',
        'price_including_transport',
        'price_per_unit_amount',
        'use_price_per_unit',
        'waste_percentage',
    )
    readonly_fields = (
        'unit_of_measure',
        'price_including_transport',
        'price_per_unit_amount',
    )
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter stock_item by current site"""
        if db_field.name == "stock_item":
            current_site = getattr(request, 'current_site', None)
            if current_site:
                # Site admin: show ONLY stock items for this site
                from inventory.models import StockItem
                kwargs["queryset"] = StockItem.objects.filter(site_id=current_site.id)
            else:
                # HQ context: show all stock items
                from inventory.models import StockItem
                kwargs["queryset"] = StockItem.objects.all()
        
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

@admin.register(ProductCosting)
class ProductCostingAdmin(SiteAwareModelAdmin, ArchivableAdmin):
    inlines = [ProductCostingStockItemInline]
    
    search_fields = ['description']
    
    list_display = [
        'product',
        'date'
    ]
    list_filter = ['date', 'category']
    search_fields = ['product__name']

    
    fieldsets = (
        ('Product Information', {
            'fields': (
                'category',
                'product',
            )
        }),
        ('Product Costing Stock Items', {
            'fields': ('stock_items_display',)
        }),
        ('Costing Records', {
            'fields': (
                ('total_stock_items_display', 'total_stock_items_incl_vat_display'),
                ('overhead_costing', 'overhead_price_per_unit_display'),
                ('salary_costing', 'salary_price_per_unit_display'),
                ('investor_loan_costing', 'investor_loan_price_per_unit_display'),
                ('use_markup', 'markup_percentage'),
                ('use_markup_percentage', 'markup_per_unit'),
                ('price',),
            )
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
    )
    
    readonly_fields = [
        'stock_items_display',
        'total_stock_items_display',
        'total_stock_items_incl_vat_display',
        'overhead_price_per_unit_display',
        'salary_price_per_unit_display',
        'investor_loan_price_per_unit_display',
        'price',
    ]
    
    class Media:
        js = (
            'js/product_costing.js',
            'js/product_costing_defaults.js',
            'js/admin_enter_fix.js',
        )
        css = {
            'all': ('css/product_costing.css',)
        }

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter overhead_costing, salary_costing, and category by current site"""
        current_site = getattr(request, 'current_site', None)
        
        if db_field.name == "overhead_costing":
            if current_site:
                # Site admin: show ONLY overhead costings for this site
                kwargs["queryset"] = OverheadCosting.objects.filter(site_id=current_site.id)
            else:
                # HQ context: show all overhead costings
                kwargs["queryset"] = OverheadCosting.objects.all()
        
        elif db_field.name == "salary_costing":
            if current_site:
                # Site admin: show ONLY salary costings for this site
                kwargs["queryset"] = SalaryCosting.objects.filter(site_id=current_site.id)
            else:
                # HQ context: show all salary costings
                kwargs["queryset"] = SalaryCosting.objects.all()
        
        elif db_field.name == "investor_loan_costing":
            if current_site:
                # Site admin: show ONLY investor/loan costings for this site
                kwargs["queryset"] = InvestorLoanCosting.objects.filter(site_id=current_site.id)
            else:
                # HQ context: show all investor/loan costings
                kwargs["queryset"] = InvestorLoanCosting.objects.all()
        
        elif db_field.name == "category":
            from product_details.models import ProductCategory
            if current_site:
                # Site admin: show ONLY product categories for this site
                kwargs["queryset"] = ProductCategory.objects.filter(site=current_site)
            else:
                # HQ context: show all product categories
                kwargs["queryset"] = ProductCategory.objects.all()
        
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def total_stock_items_display(self, obj):
        if obj:
            cur = get_company_currency()
            total = obj.total_stock_items_excl_vat
            return format_html('<strong>{} {:,.2f}</strong>', cur, float(total))
        return "-"
    total_stock_items_display.short_description = "Total Stock Items Excl VAT"

    def total_stock_items_incl_vat_display(self, obj):
        if obj:
            cur = get_company_currency()
            total = obj.total_stock_items_incl_vat
            return format_html('<strong>{} {:,.2f}</strong>', cur, float(total))
        return "-"
    total_stock_items_incl_vat_display.short_description = "Total Stock Items Incl VAT"

    total_stock_items_incl_vat_display.short_description = "Total Stock Items Incl VAT"

    def overhead_price_per_unit_display(self, obj):
        """Display overhead price per unit - uses snapshot if available"""
        if not obj:
            return "-"
        cur = get_company_currency()
        # Use the model's property which handles snapshot logic
        value = obj.overhead_price_per_unit
        if value == 0 and not obj.overhead_costing:
            return "-"
        return f"{cur} {float(value):,.2f}"
    overhead_price_per_unit_display.short_description = "Price per Unit"

    def salary_price_per_unit_display(self, obj):
        """Display salary price per unit - uses snapshot if available"""
        if not obj:
            return "-"
        cur = get_company_currency()
        # Use the model's property which handles snapshot logic
        value = obj.salary_price_per_unit
        if value == 0 and not obj.salary_costing:
            return "-"
        return f"{cur} {float(value):,.2f}"
    salary_price_per_unit_display.short_description = "Price per Unit"

    def investor_loan_price_per_unit_display(self, obj):
        """Display investor/loan price per unit - uses snapshot if available"""
        if not obj:
            return "-"
        cur = get_company_currency()
        # Use the model's property which handles snapshot logic
        value = obj.investor_loan_price_per_unit
        if value == 0 and not obj.investor_loan_costing:
            return "-"
        return f"{cur} {float(value):,.2f}"
    investor_loan_price_per_unit_display.short_description = "Price per Unit"

    def get_changeform_initial_data(self, request):
        """Pre-populate form initial data with defaults for new ProductCosting records"""
        initial = super().get_changeform_initial_data(request)
        
        from .models import OverheadCosting, SalaryCosting, InvestorLoanCosting
        
        # Set defaults for new records
        if 'overhead_costing' not in initial or initial.get('overhead_costing') is None:
            default_oh = OverheadCosting.get_default()
            if default_oh:
                initial['overhead_costing'] = default_oh.pk
        
        if 'salary_costing' not in initial or initial.get('salary_costing') is None:
            default_sal = SalaryCosting.get_default()
            if default_sal:
                initial['salary_costing'] = default_sal.pk
        
        if 'investor_loan_costing' not in initial or initial.get('investor_loan_costing') is None:
            default_il = InvestorLoanCosting.get_default()
            if default_il:
                initial['investor_loan_costing'] = default_il.pk
        
        return initial

    def change_view(self, request, object_id=None, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['product_select_disabled'] = True
        extra_context['company_currency'] = get_company_currency()
        
        # For existing records, pass original costing IDs and snapshot values for JS comparison
        if object_id:
            obj = self.get_object(request, object_id)
            if obj:
                extra_context['original_overhead_costing_id'] = obj.overhead_costing_id or ''
                extra_context['original_salary_costing_id'] = obj.salary_costing_id or ''
                extra_context['original_investor_loan_costing_id'] = obj.investor_loan_costing_id or ''
                extra_context['overhead_snapshot'] = float(obj.overhead_price_per_unit_snapshot or 0)
                extra_context['salary_snapshot'] = float(obj.salary_price_per_unit_snapshot or 0)
                extra_context['investor_loan_snapshot'] = float(obj.investor_loan_price_per_unit_snapshot or 0)
        
        response = super().change_view(request, object_id, form_url, extra_context)
        
        # Inject currency and original values as JavaScript global variables
        if hasattr(response, 'render'):
            response.render()
        
        currency = extra_context.get('company_currency', 'R')
        orig_overhead = extra_context.get('original_overhead_costing_id', '')
        orig_salary = extra_context.get('original_salary_costing_id', '')
        orig_investor_loan = extra_context.get('original_investor_loan_costing_id', '')
        overhead_snap = extra_context.get('overhead_snapshot', 0)
        salary_snap = extra_context.get('salary_snapshot', 0)
        investor_loan_snap = extra_context.get('investor_loan_snapshot', 0)
        
        script_tag = f'''<script>
            window.COMPANY_CURRENCY = "{currency}";
            window.ORIGINAL_OVERHEAD_COSTING_ID = "{orig_overhead}";
            window.ORIGINAL_SALARY_COSTING_ID = "{orig_salary}";
            window.ORIGINAL_INVESTOR_LOAN_COSTING_ID = "{orig_investor_loan}";
            window.OVERHEAD_SNAPSHOT = {overhead_snap};
            window.SALARY_SNAPSHOT = {salary_snap};
            window.INVESTOR_LOAN_SNAPSHOT = {investor_loan_snap};
        </script>'''.encode('utf-8')
        
        if hasattr(response, 'content'):
            response.content = response.content.replace(b'</head>', script_tag + b'</head>')
        
        return response

    def save_model(self, request, obj, form, change):
        """Handle ProductCosting save with snapshot update logic.
        
        If user confirms to update snapshots (via hidden field from JS popup),
        we pass update_snapshots=True to the model's save method.
        """
        # Check if user confirmed to update snapshots via POST data
        update_snapshots = request.POST.get('update_costing_snapshots') == 'true'
        
        # First call parent to handle standard save
        super().save_model(request, obj, form, change)
        
        # If update_snapshots was confirmed, re-save with the flag
        if update_snapshots:
            obj.save(update_snapshots=True)
        
        # Auto-create ProductCostingStockItem records from product components
        if obj.product and obj.stock_items.count() == 0:
            # 1. Main Product Components
            for comp in obj.product.main_product_components.all():
                ProductCostingStockItem.objects.create(
                    product_costing=obj,
                    stock_item=comp.stock_item,
                    usage_per_unit=comp.standard_usage_per_production_unit,
                )
            
            # 2. Product Components
            for comp in obj.product.components.all():
                ProductCostingStockItem.objects.create(
                    product_costing=obj,
                    stock_item=comp.stock_item,
                    usage_per_unit=comp.standard_usage_per_production_unit,
                )
            
            # 3. Recipe Items
            for recipe in obj.product.recipes.all():
                for item in recipe.items.all():
                    ProductCostingStockItem.objects.create(
                        product_costing=obj,
                        stock_item=item.stock_item,
                        usage_per_unit=item.standard_usage_per_production_unit,
                    )
    
    def stock_items_display(self, obj):
        if not obj or not obj.product:
            return "Select a product first"

        cur = get_company_currency()
        product = obj.product
        all_items = []
        
        try:
            for comp in product.main_product_components.all():
                all_items.append({
                    'name': comp.stock_item.name,
                    'usage': comp.standard_usage_per_production_unit,
                    'unit': comp.unit_of_measure,
                    'price_incl': comp.stock_item.standard_cost_incl_transport or Decimal('0.00'),
                })
            
            for comp in product.components.all():
                all_items.append({
                    'name': comp.stock_item.name,
                    'usage': comp.standard_usage_per_production_unit,
                    'unit': comp.unit_of_measure,
                    'price_incl': comp.stock_item.standard_cost_incl_transport or Decimal('0.00'),
                })
            
            for recipe in product.recipes.all():
                for item in recipe.items.all():
                    all_items.append({
                        'name': item.stock_item.name,
                        'usage': item.standard_usage_per_production_unit,
                        'unit': item.unit_of_measure,
                        'price_incl': item.stock_item.standard_cost_incl_transport or Decimal('0.00'),
                    })
        
        except Exception as e:
            return f"Error loading items: {str(e)}"
        
        if not all_items:
            return "No stock items for this product"
        
        rows = []
        for idx, item in enumerate(all_items):
            price_per_unit = Decimal(str(item['usage'])) * Decimal(str(item['price_incl']))
            rows.append(f"""
            <tr data-index="{idx}">
                <td style="border:1px solid #ddd; padding:8px;">{item['name']}</td>
                <td style="border:1px solid #ddd; padding:8px; text-align:center;">{item['usage']}</td>
                <td style="border:1px solid #ddd; padding:8px; text-align:center;">{item['unit']}</td>
                <td style="border:1px solid #ddd; padding:8px; text-align:right;">{cur} {float(item['price_incl']):,.2f}</td>
                <td style="border:1px solid #ddd; padding:8px; text-align:right;"><strong>{cur} {float(price_per_unit):,.2f}</strong></td>
                <td style="border:1px solid #ddd; padding:8px; text-align:right;">
                    <input type="number" step="0.01" value="{float(price_per_unit):.2f}"
                           class="use-price-input" data-index="{idx}" style="width:80px;">
                </td>
                <td style="border:1px solid #ddd; padding:8px; text-align:center;">
                    <input type="number" step="0.01" value="0"
                           class="waste-input" data-index="{idx}" style="width:60px;">
                </td>
            </tr>
            """)
        
        table_html = f"""
        <table style="width:100%; border-collapse:collapse; margin-top:10px; font-size:13px;" id="stock-items-table">
            <thead>
                <tr style="background-color:#e8e8e8;">
                    <th style="border:1px solid #ddd; padding:8px; text-align:left; width:25%;">Stock Item</th>
                    <th style="border:1px solid #ddd; padding:8px; text-align:center; width:8%;">Usage</th>
                    <th style="border:1px solid #ddd; padding:8px; text-align:center; width:7%;">Unit</th>
                    <th style="border:1px solid #ddd; padding:8px; text-align:center; width:12%;">Price Inc Transport</th>
                    <th style="border:1px solid #ddd; padding:8px; text-align:center; width:12%;">Price per Unit</th>
                    <th style="border:1px solid #ddd; padding:8px; text-align:center; width:12%;">Use Price per Unit</th>
                    <th style="border:1px solid #ddd; padding:8px; text-align:center; width:8%;">Waste %</th>
                </tr>
            </thead>
            <tbody>
                {''.join(rows)}
            </tbody>
        </table>
        """
        
        return mark_safe(table_html)

    stock_items_display.short_description = "Product Stock Items"

class BillingDocumentHeaderForm(forms.ModelForm):
    production_dates = forms.CharField(
        required=False,
        label="Production Dates",
        widget=forms.TextInput(attrs={
            'placeholder': '',
            'size': 60,
            'class': 'vTextField',
            'autocomplete': 'off',
        }),
        help_text="Enter dates as DD-MM-YYYY, separated by commas.",
    )

    billing_date = forms.DateField(
        required=True,
        input_formats=DATE_INPUTS_BILLING,
        widget=forms.DateInput(
            format='%d-%m-%Y',
            attrs={'class': 'vDateField', 'size': 10},
        ),
    )
    due_date = forms.DateField(
        required=False,
        input_formats=DATE_INPUTS_BILLING,
        widget=forms.DateInput(
            format='%d-%m-%Y',
            attrs={'class': 'vDateField', 'size': 10},
        ),
    )

    class Meta:
        model = BillingDocumentHeader
        # Explicitly list all model fields - production_dates is a custom form field, not a model field
        fields = [
            'site', 'batch_costings', 'production_dates_text',
            'company', 'client', 'delivery_institution', 'transporters', 'base_number',
            'bill_per_pallet', 'bill_per_secondary', 'bill_per_primary',
            'billing_date', 'due_date',
            'from_currency', 'to_currency', 'exchange_rate', 'vat_percentage',
            'transport_cost',
            'create_quote', 'create_proforma', 'create_invoice',
            'create_picking_slip', 'create_delivery_note',
            'qty_for_invoice_data',
        ]
        widgets = {
            'qty_for_invoice_data': forms.Textarea(),
            'billing_date': forms.DateInput(
                format='%d/%m/%Y',
                attrs={'class': 'vDateField', 'size': 10}
            ),
            'due_date': forms.DateInput(
                format='%d/%m/%Y',
                attrs={'class': 'vDateField', 'size': 10}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # TEMPORARILY COMMENTED OUT FOR TESTING
        if 'batch_costings' in self.fields:
            self.fields['batch_costings'].widget = forms.CheckboxSelectMultiple()

        from datetime import datetime

        # Only populate production_dates if the field exists (it may be excluded in HQ admin)
        if 'production_dates' in self.fields:
            if self.instance.pk and self.instance.production_dates_text:
                date_strings = [
                    d.strip()
                    for d in self.instance.production_dates_text.split(",")
                    if d.strip()
                ]
                formatted_dates = []
                for ds in date_strings:
                    try:
                        date_obj = datetime.strptime(ds, "%Y-%m-%d")
                        formatted_dates.append(date_obj.strftime("%d/%m/%Y"))
                    except ValueError:
                        formatted_dates.append(ds)
                self.fields['production_dates'].initial = ", ".join(formatted_dates) if formatted_dates else ""
            else:
                # No stored text (add form or empty), force blank
                self.fields['production_dates'].initial = ""

        # Setup delivery_institution field with dynamic filtering
        if 'delivery_institution' in self.fields:
            # If editing existing object with a client, filter by that client
            if self.instance.pk and self.instance.client_id:
                self.fields['delivery_institution'].queryset = DeliverySite.objects.filter(
                    client=self.instance.client
                ).order_by('institutionname')
            else:
                # Empty queryset initially (will be populated by client selection)
                self.fields['delivery_institution'].queryset = DeliverySite.objects.none()
            
            # Add data attribute for JavaScript to enable dynamic filtering
            self.fields['delivery_institution'].widget.attrs['data-chained-field'] = 'client'

    def clean(self):
        """Validate that delivery_institution belongs to the selected client"""
        cleaned_data = super().clean()
        client = cleaned_data.get('client')
        delivery_institution = cleaned_data.get('delivery_institution')
        
        if delivery_institution and client:
            # Verify that the institution belongs to the selected client
            if delivery_institution.client_id != client.id:
                raise forms.ValidationError(
                    f"The selected institution '{delivery_institution.institutionname}' does not belong to client '{client.name}'."
                )
        
        return cleaned_data


    def save(self, commit=True):
        from datetime import datetime
        
        instance = super().save(commit=False)
        
        # Only process production_dates if the field exists (it may be excluded in HQ admin)
        if 'production_dates' in self.fields:
            # Get raw input
            raw = self.cleaned_data.get("production_dates") or ""
            
            # Parse and normalize dates to YYYY-MM-DD
            date_strings = [d.strip() for d in raw.split(",") if d.strip()]
            normalized_dates = []
            
            for ds in date_strings:
                try:
                    # Try DD/MM/YYYY format first
                    date_obj = datetime.strptime(ds, "%d/%m/%Y")
                    normalized_dates.append(date_obj.strftime("%Y-%m-%d"))
                except ValueError:
                    try:
                        # Try YYYY-MM-DD format as fallback
                        date_obj = datetime.strptime(ds, "%Y-%m-%d")
                        normalized_dates.append(date_obj.strftime("%Y-%m-%d"))
                    except ValueError:
                        continue
            
            # Store normalized dates
            instance.production_dates_text = ", ".join(normalized_dates)
            
            # Store for later M2M processing
            self._normalized_dates = normalized_dates
        
        if commit:
            instance.save()
            self.save_m2m()
        
        return instance

    def _save_m2m(self):
        """Override to populate batch_costings from production_dates_text"""
        from datetime import datetime
        from manufacturing.models import Production
        from costing.models import BatchCosting
        
        super()._save_m2m()
        
        if not hasattr(self, '_normalized_dates'):
            return
        
        batch_costing_ids = []
        seen = set()
        
        for ds in self._normalized_dates:
            try:
                # ds is already YYYY-MM-DD from form.save()
                date_obj = datetime.strptime(ds, "%Y-%m-%d").date()
                
                # Find Production for this date AND same site
                prod = Production.objects.filter(
                    production_date=date_obj,
                    site=self.instance.site
                ).first()
                if not prod:
                    continue
                
                # Find BatchCosting for this Production
                bc = BatchCosting.objects.filter(production_date=prod).first()
                if bc and bc.pk not in seen:
                    batch_costing_ids.append(bc.pk)
                    seen.add(bc.pk)
            except ValueError:
                continue
        
        if batch_costing_ids:
            self.instance.batch_costings.set(batch_costing_ids)

@admin.register(BillingDocumentHeader)
class BillingDocumentHeaderAdmin(SiteAwareModelAdmin, ArchivableAdmin):
    change_list_template = "admin/archivable_change_list.html" 
    form = BillingDocumentHeaderForm
    
    search_fields = ['base_number', 'client__name']
    
    list_display = [
        'base_number',
        'batch_costings_display',
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

    readonly_fields = [
        'batch_pricing_preview_container',
        'quote_created',
        'proforma_created',
        'invoice_created',
        'picking_slip_created',
        'delivery_note_created',
        'view_quote',
        'view_proforma',
        'view_invoice',
        'view_picking_slip',
        'view_delivery_note',
        'email_quote',
        'email_proforma',
        'email_invoice',
        'email_picking_slip',
        'email_delivery_note',
        'date_created',
    ]

    autocomplete_fields = ('client', 'transporters')

    class Media:
        css = {
            'all': ('css/custom_admin.css',)
        }
        js = ('js/billing_header.js',)

    fieldsets = (
        (None, {
            'fields': ('client', 'delivery_institution', 'base_number'),
        }),
        ("Dates", {
            'fields': (('billing_date', 'due_date'),),
        }),
        ("Production Dates", {
            'fields': ('production_dates',),   # only the nice product-costing-style field
        }),
        ('Batch Selection', {
            'fields': ('batch_costings',),
        }),
        ("Batch pricing & approval", {
            'fields': ('batch_pricing_preview_container',),
        }),
        ("Financials", {
            'fields': (('from_currency', 'to_currency', 'exchange_rate', 'vat_percentage'),),
        }),
        ("Billing Method", {
            'classes': ('billing-method',),   
            'fields': (('bill_per_primary', 'bill_per_secondary', 'bill_per_pallet'),),
        }),
        ("Transport", {
            'fields': (('transporters', 'transport_cost'),),
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
    
    def change_view(self, request, object_id=None, form_url='', extra_context=None):
        """Add current site to context for JavaScript to access"""
        extra_context = extra_context or {}
        
        # Pass current site to template for JavaScript
        current_site = getattr(request, 'current_site', None)
        if current_site:
            extra_context['current_site_id'] = current_site.pk
            extra_context['current_site_name'] = current_site.name
        
        return super().change_view(request, object_id, form_url, extra_context)
    
    def add_view(self, request, form_url='', extra_context=None):
        """Add current site to context for JavaScript to access"""
        extra_context = extra_context or {}
        
        # Pass current site to template for JavaScript
        current_site = getattr(request, 'current_site', None)
        if current_site:
            extra_context['current_site_id'] = current_site.pk
            extra_context['current_site_name'] = current_site.name
        
        return super().add_view(request, form_url, extra_context)
    
    def formfield_for_manytomany(self, db_field, request=None, **kwargs):
        """Filter batch_costings to only show batches from current site"""
        if db_field.name == "batch_costings":
            current_site = getattr(request, 'current_site', None)
            if current_site:
                # Site admin - only show batch costings from productions at this site
                from manufacturing.models import Production
                site_productions = Production.objects.filter(site=current_site)
                kwargs['queryset'] = BatchCosting.objects.filter(
                    production_date__in=site_productions
                )
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def _eye_icon(self, enabled, url=None, doc_type=None):
        if enabled and url:
            return format_html(
                '<a href="{}" target="_blank" title="View document" style="font-size: 16px; margin-left: 8px;" class="billing-preview-link" data-doc-type="{}">',
                url,
                doc_type or '',
            ) + mark_safe('<i class="fa fa-eye"></i></a>')
        return mark_safe(
            '<span style="color:#ccc; font-size: 16px; margin-left: 8px;" title="Not generated yet">'
            '<i class="fa fa-eye-slash"></i>'
            '</span>'
        )

    def save_model(self, request, obj, form, change):
        try:
            super().save_model(request, obj, form, change)
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise

    @admin.display(description="Production Dates")
    def batch_costings_display(self, obj):
        """Display production dates from text field or batch_costings in DD/MM/YYYY format"""
        from datetime import datetime
        
        if obj.production_dates_text:
            # Parse and reformat dates from YYYY-MM-DD to DD/MM/YYYY
            date_strings = [d.strip() for d in obj.production_dates_text.split(",") if d.strip()]
            formatted_dates = []
            
            for ds in date_strings:
                try:
                    # Parse YYYY-MM-DD format
                    date_obj = datetime.strptime(ds, "%Y-%m-%d")
                    # Format as DD/MM/YYYY
                    formatted_dates.append(date_obj.strftime("%d/%m/%Y"))
                except ValueError:
                    # If already in different format, keep as-is
                    formatted_dates.append(ds)
            
            return ", ".join(formatted_dates)
        
        # Fallback to batch_costings if text field is empty
        costings = obj.batch_costings.all()
        if costings.exists():
            return ", ".join([str(c) for c in costings])
        return "-"


    @admin.display(description="")
    def view_quote(self, obj):
        if not obj or not obj.pk or not obj.create_quote:
            return self._eye_icon(False)
        url = reverse("costing:billing_document_preview", args=[obj.pk, "QUOTE"])
        return self._eye_icon(True, url, "QUOTE")

    @admin.display(description="")
    def view_proforma(self, obj):
        if not obj or not obj.pk or not obj.create_proforma:
            return self._eye_icon(False)
        url = reverse("costing:billing_document_preview", args=[obj.pk, "PROFORMA"])
        return self._eye_icon(True, url, "PROFORMA")

    @admin.display(description="")
    def view_invoice(self, obj):
        if not obj or not obj.pk or not obj.create_invoice:
            return self._eye_icon(False)
        url = reverse("costing:billing_document_preview", args=[obj.pk, "INVOICE"])
        return self._eye_icon(True, url, "INVOICE")

    @admin.display(description="")
    def view_picking_slip(self, obj):
        if not obj or not obj.pk or not obj.create_picking_slip:
            return self._eye_icon(False)
        url = reverse("costing:billing_document_preview", args=[obj.pk, "PICKING"])
        return self._eye_icon(True, url, "PICKING")

    @admin.display(description="")
    def view_delivery_note(self, obj):
        if not obj or not obj.pk or not obj.create_delivery_note:
            return self._eye_icon(False)
        url = reverse("costing:billing_document_preview", args=[obj.pk, "DELIVERY"])
        return self._eye_icon(True, url, "DELIVERY")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('client').prefetch_related('batch_costings')

    def batch_pricing_preview_container(self, obj):
        return mark_safe(
            '<div class="batch_pricing_preview_container" style="border:none; padding:0; margin:0;">'
            '<div class="grp-readonly" style="border:none; padding:0;"></div>'
            '</div>'
        )

    @admin.display(description="")
    def email_quote(self, obj):
        if not obj or not obj.pk or not obj.create_quote:
            return mark_safe('<span style="color:#ccc; font-size: 16px; margin-left: 8px;"><i class="fa fa-envelope"></i></span>')
        url = reverse("costing:email_billing_document", args=[obj.pk, "QUOTE"])
        return format_html('<a href="{}" target="_blank" title="Email document" style="font-size: 16px; margin-left: 8px;"><i class="fa fa-envelope"></i></a>', url)

    @admin.display(description="")
    def email_proforma(self, obj):
        if not obj or not obj.pk or not obj.create_proforma:
            return mark_safe('<span style="color:#ccc; font-size: 16px; margin-left: 8px;"><i class="fa fa-envelope"></i></span>')
        url = reverse("costing:email_billing_document", args=[obj.pk, "PROFORMA"])
        return format_html('<a href="{}" target="_blank" title="Email document" style="font-size: 16px; margin-left: 8px;"><i class="fa fa-envelope"></i></a>', url)

    @admin.display(description="")
    def email_invoice(self, obj):
        if not obj or not obj.pk or not obj.create_invoice:
            return mark_safe('<span style="color:#ccc; font-size: 16px; margin-left: 8px;"><i class="fa fa-envelope"></i></span>')
        url = reverse("costing:email_billing_document", args=[obj.pk, "INVOICE"])
        return format_html('<a href="{}" target="_blank" title="Email document" style="font-size: 16px; margin-left: 8px;"><i class="fa fa-envelope"></i></a>', url)

    @admin.display(description="")
    def email_picking_slip(self, obj):
        if not obj or not obj.pk or not obj.create_picking_slip:
            return mark_safe('<span style="color:#ccc; font-size: 16px; margin-left: 8px;"><i class="fa fa-envelope"></i></span>')
        url = reverse("costing:email_billing_document", args=[obj.pk, "PICKING"])
        return format_html('<a href="{}" target="_blank" title="Email document" style="font-size: 16px; margin-left: 8px;"><i class="fa fa-envelope"></i></a>', url)

    @admin.display(description="")
    def email_delivery_note(self, obj):
        if not obj or not obj.pk or not obj.create_delivery_note:
            return mark_safe('<span style="color:#ccc; font-size: 16px; margin-left: 8px;"><i class="fa fa-envelope"></i></span>')
        url = reverse("costing:email_billing_document", args=[obj.pk, "DELIVERY"])
        return format_html('<a href="{}" target="_blank" title="Email document" style="font-size: 16px; margin-left: 8px;"><i class="fa fa-envelope"></i></a>', url)

    batch_pricing_preview_container.short_description = "Batch Pricing & Approvals (Live Preview)"