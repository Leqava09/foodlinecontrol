from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django import forms
import nested_admin
import json
from .models import (
    Product, ProductComponent, ProductCategory, ProductRecipe, 
    ProductRecipeItem, RecipeCategory, MainProductComponent,
)
from foodlinecontrol.admin_base import ArchivableAdmin
from tenants.admin_utils import SiteAwareModelAdmin

class ProductRecipeItemInline(admin.TabularInline):
    """Items within a recipe"""
    model = ProductRecipeItem
    extra = 0
    fields = ['category', 'sub_category', 'stock_item', 'standard_usage_per_production_unit', 'unit_of_measure_display']
    readonly_fields = ['unit_of_measure_display']
    verbose_name = "Recipe Item"
    verbose_name_plural = "Recipe Items"
    can_delete = True
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter dropdowns by current site"""
        current_site = getattr(request, 'current_site', None)
        
        if current_site:
            if db_field.name == "category":
                from inventory.models import StockCategory
                kwargs["queryset"] = StockCategory.objects.filter(site=current_site)
            elif db_field.name == "sub_category":
                from inventory.models import StockSubCategory
                kwargs["queryset"] = StockSubCategory.objects.filter(site=current_site)
            elif db_field.name == "stock_item":
                from inventory.models import StockItem
                kwargs["queryset"] = StockItem.objects.filter(site=current_site)
        
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    def unit_of_measure_display(self, obj):
        if obj.unit_of_measure:
            return obj.unit_of_measure.abbreviation or obj.unit_of_measure.name
        return "-"
    unit_of_measure_display.short_description = "Unit of Measure"

class ProductRecipeInline(nested_admin.NestedTabularInline):
    """Recipe with nested items"""
    model = ProductRecipe
    extra = 0
    fields = ['recipe_category', 'recipe_name', 'standard_usage_per_production_unit', 'measure_unit']
    verbose_name = "Recipe"
    verbose_name_plural = "Recipes"
    inlines = [ProductRecipeItemInline]
    can_delete = True
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter recipe_category dropdown by current site"""
        current_site = getattr(request, 'current_site', None)
        
        if current_site and db_field.name == "recipe_category":
            kwargs["queryset"] = RecipeCategory.objects.filter(site=current_site)
        
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
class MainStockItemInline(nested_admin.NestedTabularInline):
    """Main Stock Items"""
    model = ProductComponent
    fk_name = 'product'
    extra = 0
    fields = ['category', 'sub_category', 'stock_item', 'is_primary_packaging', 'is_secondary_packaging', 'is_pallet', 'usage_per_pallet', 'standard_usage_per_production_unit', 'unit_of_measure_display']
    readonly_fields = ['unit_of_measure_display', 'standard_usage_per_production_unit']
    verbose_name = "Product Stock Item"
    verbose_name_plural = "Product Stock Items"
    can_delete = True
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter dropdowns by current site"""
        current_site = getattr(request, 'current_site', None)
        
        if current_site:
            if db_field.name == "category":
                from inventory.models import StockCategory
                kwargs["queryset"] = StockCategory.objects.filter(site=current_site)
            elif db_field.name == "sub_category":
                from inventory.models import StockSubCategory
                kwargs["queryset"] = StockSubCategory.objects.filter(site=current_site)
            elif db_field.name == "stock_item":
                from inventory.models import StockItem
                kwargs["queryset"] = StockItem.objects.filter(site=current_site)
        
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    def unit_of_measure_display(self, obj):
        if obj.unit_of_measure:
            return obj.unit_of_measure.abbreviation or obj.unit_of_measure.name
        return "-"
    unit_of_measure_display.short_description = "Unit of Measure"
    
    def get_queryset(self, request):
        """Only show main stock items (no sub-items)"""
        qs = super().get_queryset(request)
        return qs.filter(main_stock_item__isnull=True)
        
    def get_model_perms(self, request):
        """Hide from admin index/dashboard"""
        return {}


class MainProductComponentInline(nested_admin.NestedTabularInline):
    """Main Product Component - Empty by default, add items manually"""
    model = MainProductComponent
    extra = 0
    fields = ['category', 'sub_category', 'stock_item', 'standard_usage_per_production_unit', 'unit_of_measure_display']
    readonly_fields = ['unit_of_measure_display']
    verbose_name = "Main Product Component"
    verbose_name_plural = "Main Product Components"
    can_delete = True
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter dropdowns by current site"""
        current_site = getattr(request, 'current_site', None)
        
        if current_site:
            if db_field.name == "category":
                from inventory.models import StockCategory
                kwargs["queryset"] = StockCategory.objects.filter(site=current_site)
            elif db_field.name == "sub_category":
                from inventory.models import StockSubCategory
                kwargs["queryset"] = StockSubCategory.objects.filter(site=current_site)
            elif db_field.name == "stock_item":
                from inventory.models import StockItem
                kwargs["queryset"] = StockItem.objects.filter(site=current_site)
        
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def unit_of_measure_display(self, obj):
        if obj.unit_of_measure:
            return obj.unit_of_measure.abbreviation or obj.unit_of_measure.name
        return "-"
    unit_of_measure_display.short_description = "Unit of Measure"
    
    def get_model_perms(self, request):
        """Hide from admin index/dashboard"""
        return {}
        

@admin.register(Product)
class ProductAdmin(SiteAwareModelAdmin, ArchivableAdmin, nested_admin.NestedModelAdmin):
    list_display = ['product_name', 'category', 'component_count', 'recipe_count', 'components_data']
    list_filter = ['category']
    
    def get_queryset(self, request):
        """Filter products by current site"""
        qs = super().get_queryset(request)
        current_site = getattr(request, 'current_site', None)
        if current_site:
            # Site admin context - filter by site
            qs = qs.filter(site=current_site)
        return qs
    
    def save_model(self, request, obj, form, change):
        """Automatically set site when saving from site admin context"""
        current_site = getattr(request, 'current_site', None)
        if current_site and not change:
            # Creating new product - always set to current site
            obj.site = current_site
        elif current_site and change:
            # Editing existing product - keep the site assignment
            obj.site = current_site
        super().save_model(request, obj, form, change)
    
    def get_form(self, request, obj=None, **kwargs):
        """Override form to filter category choices by site and set widget styles"""
        form = super().get_form(request, obj, **kwargs)
        
        # Filter category dropdown based on site context
        if 'category' in form.base_fields:
            current_site = getattr(request, 'current_site', None)
            if current_site:
                # Site admin: show ONLY categories for this site (no cross-site access)
                form.base_fields['category'].queryset = ProductCategory.objects.filter(site=current_site)
            else:
                # HQ context - show all categories across all sites
                form.base_fields['category'].queryset = ProductCategory.objects.all()
            
            # Set category widget style
            form.base_fields['category'].widget.attrs.update({
                'style': 'max-width: 250px; height: 28px; padding: 4px 8px;'
            })
        
        # Set product_name widget style
        if 'product_name' in form.base_fields:
            form.base_fields['product_name'].widget.attrs.update({
                'style': 'max-width: 400px; height: 28px; padding: 4px 8px;'
            })
        
        return form
    
    fieldsets = (
    ('Product Information', {
        'classes': ('wide', 'extrapretty'),
        'fields': (
            'category',                 
            ('product_name', 'size', 'sku'),   
            'requires_nsi_nrcs_certification',  
        ),
    }),
)
    
    inlines = [MainProductComponentInline, MainStockItemInline, ProductRecipeInline]
    
    class Media:
        js = (
            'js/unit_autofill_grappelli.js',
            'js/recipe_category_edit_icon.js',
            'js/product_category_edit_icon.js',
        )
        css = {
            'all': ('css/product_admin.css',)
        }
        
    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        """✅ Inject packaging info as JSON for batch detail page"""
        extra_context = extra_context or {}
        
        if object_id:
            try:
                product = Product.objects.get(pk=object_id)
                packaging_info = ProductComponent.get_packaging_info(product)
                extra_context['packaging_info_json'] = json.dumps(packaging_info)
            except Product.DoesNotExist:
                pass
        
        return super().changeform_view(request, object_id, form_url, extra_context)  # ✅ RETURN!
    
    def component_count(self, obj):
        return obj.components.filter(main_stock_item__isnull=True).count()
    component_count.short_description = "Product Stock Items"
    
    def recipe_count(self, obj):
        return obj.recipes.count()
    recipe_count.short_description = "Recipes"
    
    def components_data(self, obj):
        components = obj.components.filter(main_stock_item__isnull=True)
        if not components.exists():
            return ""
        
        data = []
        for comp in components:
            cat = comp.category.name if comp.category else "-"
            sub_cat = comp.sub_category.name if comp.sub_category else "-"
            stock = str(comp.stock_item) if comp.stock_item else "-"
            usage = str(comp.standard_usage_per_production_unit) if comp.standard_usage_per_production_unit else "-"
            unit = comp.unit_of_measure.abbreviation if comp.unit_of_measure and comp.unit_of_measure.abbreviation else (comp.unit_of_measure.name if comp.unit_of_measure else "-")
            data.append(f"{cat}|{sub_cat}|{stock}|{usage}|{unit}")
        
        return " ".join(data)
    
    def changelist_view(self, request, extra_context=None):
        """Override to inject product component data as JSON for frontend rendering"""
        response = super().changelist_view(request, extra_context or {})

        try:
            products_by_category = {}
            categories_list = []

            # Use get_queryset to respect site filtering
            for product in self.get_queryset(request).select_related('category').prefetch_related('components', 'main_product_components', 'recipes__items'):
                components = product.components.filter(main_stock_item__isnull=True)
                main_product_components = product.main_product_components.all()
                recipes = product.recipes.all()
                
                category_name = product.category.name if product.category else 'Other'
                
                if category_name not in products_by_category:
                    products_by_category[category_name] = []
                    categories_list.append(category_name)
                
                component_list = []
                mpc_count = 0
                
                for mpc in main_product_components:
                    component_list.append({
                        'category': mpc.category.name if mpc.category else '-',
                        'sub_category': mpc.sub_category.name if mpc.sub_category else '-',
                        'stock_item': str(mpc.stock_item) if mpc.stock_item else '-',
                        'usage': str(mpc.standard_usage_per_production_unit) if mpc.standard_usage_per_production_unit else '-',
                        'unit': mpc.unit_of_measure.abbreviation if mpc.unit_of_measure and mpc.unit_of_measure.abbreviation else (mpc.unit_of_measure.name if mpc.unit_of_measure else '-')
                    })
                    mpc_count += 1

                for comp in components:
                    component_list.append({
                        'category': comp.category.name if comp.category else '-',
                        'sub_category': comp.sub_category.name if comp.sub_category else '-',
                        'stock_item': str(comp.stock_item) if comp.stock_item else '-',
                        'usage': str(comp.standard_usage_per_production_unit) if comp.standard_usage_per_production_unit else '-',
                        'unit': comp.unit_of_measure.abbreviation if comp.unit_of_measure and comp.unit_of_measure.abbreviation else (comp.unit_of_measure.name if comp.unit_of_measure else '-')
                    })
                
                recipe_list = []
                for recipe in recipes:
                    recipe_items = []
                    for item in recipe.items.all():
                        recipe_items.append({
                            'category': item.category.name if item.category else '-',
                            'sub_category': item.sub_category.name if item.sub_category else '-',
                            'stock_item': str(item.stock_item) if item.stock_item else '-',
                            'usage': str(item.standard_usage_per_production_unit) if item.standard_usage_per_production_unit else '-',
                            'unit': item.unit_of_measure.abbreviation if item.unit_of_measure and item.unit_of_measure.abbreviation else (item.unit_of_measure.name if item.unit_of_measure else '-')
                        })
                    
                    recipe_list.append({
                        'recipe_category': recipe.recipe_category.name if recipe.recipe_category else '-',
                        'recipe_name': recipe.recipe_name,
                        'standard_usage_per_production_unit': str(recipe.standard_usage_per_production_unit) if recipe.standard_usage_per_production_unit else '-',  
                        'measure_unit': recipe.measure_unit or '-',
                        'items': recipe_items
                    })
                
                edit_url = reverse('admin:product_details_product_change', args=[product.pk])
                products_by_category[category_name].append({
                    'id': product.pk,
                    'name': product.product_name,
                    'size': product.size or '-',
                    'edit_url': edit_url,
                    'components': component_list,
                    'main_product_component_count': mpc_count,
                    'recipes': recipe_list
                })
                
            categories_list = sorted(categories_list)
            
            data_json = json.dumps({
                'products_by_category': products_by_category,
                'categories': categories_list
            })

            if hasattr(response, 'render'):
                response.render()

            injection = f"""
            <div class="results-content"></div>
            <script src="/static/js/product-list-table.js"></script>
            <script>
            window.PRODUCT_DATA = {data_json};
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

    
@admin.register(ProductCategory)
class ProductCategoryAdmin(SiteAwareModelAdmin, admin.ModelAdmin):
    list_display = ['name', 'product_list']
    search_fields = ['name']
    
    def get_queryset(self, request):
        """Filter categories by current site"""
        qs = super().get_queryset(request)
        current_site = getattr(request, 'current_site', None)
        if current_site:
            qs = qs.filter(site=current_site)
        return qs
    
    def save_model(self, request, obj, form, change):
        """Automatically set site when saving from site admin context"""
        current_site = getattr(request, 'current_site', None)
        if current_site:
            obj.site = current_site
        super().save_model(request, obj, form, change)
    
    def product_list(self, obj):
        """Display product names stacked vertically"""
        products = obj.products.all()
        if not products.exists():
            return "-"
        product_names = "<br>".join([p.product_name for p in products])
        return format_html(product_names)
    product_list.short_description = "Products"
    
    def get_model_perms(self, request):
        return {}
        
class RecipeCategoryAdmin(SiteAwareModelAdmin, admin.ModelAdmin):
    list_display = ['name', 'recipe_count']
    search_fields = ['name']
    fieldsets = (
        ('Recipe Category', {
            'fields': ('name',)
        }),
    )
    
    def get_queryset(self, request):
        """Filter recipe categories by current site"""
        qs = super().get_queryset(request)
        current_site = getattr(request, 'current_site', None)
        if current_site:
            qs = qs.filter(site=current_site)
        return qs
    
    def save_model(self, request, obj, form, change):
        """Automatically set site when saving from site admin context"""
        current_site = getattr(request, 'current_site', None)
        if current_site:
            obj.site = current_site
        super().save_model(request, obj, form, change)
    
    def recipe_count(self, obj):
        count = obj.productrecipe_set.count()
        return count
    recipe_count.short_description = "Recipes Using This"
    
    def has_delete_permission(self, request, obj=None):
        """Block delete if recipes exist"""
        if obj and obj.productrecipe_set.exists():
            return False
        return True
    
    def delete_model(self, request, obj):
        """Delete recipes first, then category"""
        if obj.productrecipe_set.exists():
            obj.productrecipe_set.all().delete()
        super().delete_model(request, obj)
        
    def get_model_perms(self, request):
        """Hide from admin index/dashboard"""
        return {}

class ProductRecipeAdmin(nested_admin.NestedModelAdmin):
    """Admin for managing recipes separately"""
    list_display = ['recipe_name', 'product', 'recipe_category', 'item_count']
    list_filter = ['product', 'recipe_category']
    search_fields = ['recipe_name', 'product__product_name']
    ordering = ['product', 'recipe_category', 'recipe_name']
    
    fieldsets = (
        ('Recipe Information', {
            'classes': ('wide', 'extrapretty'),
            'fields': ('product', 'recipe_category', 'recipe_name', 'standard_usage_per_production_unit', 'order')
        }),
    )
    
    inlines = [ProductRecipeItemInline]
    
    def item_count(self, obj):
        return obj.items.count()
    item_count.short_description = "Items"
    
    def get_model_perms(self, request):
        """Hide from admin index/dashboard"""
        return {}

class MainProductComponentAdmin(admin.ModelAdmin):
    list_display = ['product', 'stock_item', 'standard_usage_per_production_unit', 'unit_of_measure']
    list_filter = ['product', 'category']
    search_fields = ['product__product_name', 'stock_item__name']
    ordering = ['product', 'id']
    
    def get_model_perms(self, request):
        """Hide from admin index/dashboard"""
        return {}

# Register RecipeCategory
admin.site.register(RecipeCategory, RecipeCategoryAdmin)        

# Also register these if not already registered
admin.site.register(ProductRecipe, ProductRecipeAdmin)
admin.site.register(MainProductComponent, MainProductComponentAdmin)

