from django.contrib import admin
from django.utils.html import format_html
from django.urls import path
from django.shortcuts import render, get_object_or_404, redirect
from django import forms
from django.utils.safestring import mark_safe
from decimal import Decimal
from inventory.models import StockCategory, StockSubCategory
from django.utils.formats import date_format
from .forms import WarehouseAdminForm
from commercial.models import CompanyDetails
from .models import (
    Supplier,
    Client,
    Warehouse,
    Transporter,
    CompanyDetails,
    StandardTransportRate,
)
from foodlinecontrol.admin_base import ArchivableAdmin
from tenants.admin_utils import SiteAwareModelAdmin

class StandardTransportRateInline(admin.TabularInline):
    model = StandardTransportRate
    extra = 0
    fields = ("from_location", "to_location", "currency", "amount_excl")

@admin.register(Client)
class ClientAdmin(SiteAwareModelAdmin, ArchivableAdmin): 
    list_display = ("name", "legal_name", "phone", "email", "city", "country")
    search_fields = (
        "name",
        "legal_name",
        "registration_number",
        "vat_number",
        "email",
        "phone",
        "city",
    )
    list_filter = ("city", "province", "country")

    fieldsets = (
        ("Identity", {
            "fields": (
                "name",
                "legal_name",
                "registration_number",
                "vat_number",
            )
        }),
        ("Address", {
            "fields": (
                "address_line1",
                "address_line2",
                "city",
                "province",
                "postal_code",
                "country",
            )
        }),
        ("Contact & terms", {
            "fields": (
                "contact_person",
                "phone",
                "email",
                "payment_terms",
            )
        }),
        ("Additional", {
            "fields": (
                "notes",
            )
        }),
    )

@admin.register(Warehouse)
class WarehouseAdmin(SiteAwareModelAdmin, ArchivableAdmin): 
    form = WarehouseAdminForm
   
    list_display = ("warehouse_name", "city", "province", "lease_expiry_display", "manager")
    
    def lease_expiry_display(self, obj):
        if not obj.lease_expiry_date:
            return "-"
        return date_format(obj.lease_expiry_date, "d-m-Y")
    lease_expiry_display.short_description = "Expiry date of lease"
    lease_expiry_display.admin_order_field = "lease_expiry_date"
    
    search_fields = ("warehouse_name", "city", "province", "postal_code", "manager")
    list_filter = ("city", "province", "country", "lease_expiry_date", "manager")

    fieldsets = (
        ("Identity", {
            "fields": ("warehouse_name",)
        }),
        ("Lease details", {
            "fields": (
                "size_m2",
                "standard_rate_per_m2_per_month",
                "total_rent_per_month",
                "lease_expiry_date",
            )
        }),
        ("Contact", {
            "fields": ("manager", "phone", "email")
        }),
        ("Address", {
            "fields": (
                "address_line1",
                "address_line2",
                "city",
                "province",
                "postal_code",
                "country",
            )
        }),
        ("Additional", {
            "fields": ("notes",)
        }),
    )
    
@admin.register(Transporter)
class TransporterAdmin(SiteAwareModelAdmin, ArchivableAdmin):
    list_display = ("name", "contact_person", "email", "phone")
    search_fields = ("name", "contact_person", "email", "phone")
    
    inlines = [StandardTransportRateInline]

@admin.register(Supplier)
class SupplierAdmin(SiteAwareModelAdmin, ArchivableAdmin):
    list_display = ('name', 'category', 'sub_category', 'contact_person', 'email', 'phone')
    list_filter = ('category', 'sub_category')
    search_fields = ('name', 'contact_person', 'email', 'phone', 'address')
    
    fieldsets = (
        ('Identity', {
            'fields': ('name',)
        }),
        ('Classification', {
            'fields': ('category', 'sub_category')
        }),
        ('Contact', {
            'fields': ('contact_person', 'email', 'phone')
        }),
        ('Address', {
            'fields': ('address',)
        }),
        ('Additional', {
            'fields': ('notes',)
        }),
    )
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter category and sub_category by site"""
        current_site = getattr(request, 'current_site', None)
        
        if db_field.name == "category":
            if current_site:
                # Site admin: show only categories for this site
                kwargs["queryset"] = StockCategory.objects.filter(site=current_site)
            else:
                # HQ admin: show only HQ categories (site=NULL)
                kwargs["queryset"] = StockCategory.objects.filter(site__isnull=True)
        
        # Note: sub_category is ChainedForeignKey, so it auto-filters based on category selection
        # But we should also ensure subcategories respect site boundaries
        if db_field.name == "sub_category":
            if current_site:
                kwargs["queryset"] = StockSubCategory.objects.filter(site=current_site)
            else:
                kwargs["queryset"] = StockSubCategory.objects.filter(site__isnull=True)
        
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

@admin.register(CompanyDetails)
class CompanyDetailsAdmin(SiteAwareModelAdmin, ArchivableAdmin): 
    list_display = ["name", "vat_number", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name", "legal_name", "vat_number", "registration_number"]

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
        # Admin Appearance moved to Site model in HQ Admin
        ("Status", {
            "fields": ("is_active",),
        }),
    )
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == "currency":
            formfield.widget.attrs["style"] = "width:80px; text-align:left;"
        return formfield
