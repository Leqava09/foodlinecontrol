from django.db import models
from decimal import Decimal
from smart_selects.db_fields import ChainedForeignKey


class ProductCategory(models.Model):
    site = models.ForeignKey(
        'tenants.Site',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='product_categories'
    )
    name = models.CharField(max_length=255)

    class Meta:
        verbose_name = "Product Category"
        verbose_name_plural = "Product Categories"
        ordering = ['name']

    def __str__(self):
        return self.name


class IngredientType(models.Model):
    name = models.CharField(max_length=50, unique=True)

    class Meta:
        verbose_name = "Ingredient Type"
        verbose_name_plural = "Ingredient Types"

    def __str__(self):
        return self.name


class Product(models.Model):
    site = models.ForeignKey(
        'tenants.Site',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='products'
    )
    product_name = models.CharField(max_length=255)
    sku = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="SKU",
    )
    category = models.ForeignKey(
        ProductCategory,
        on_delete=models.PROTECT,
        related_name='products'
    )
    size = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Size",
    )
    requires_nsi_nrcs_certification = models.BooleanField(
        default=True,
        verbose_name="Requires NSI / NRCS Certification",
        help_text="Check if this product requires NSI or NRCS certification after manufacturing"
    )
    
    is_archived = models.BooleanField(default=False, db_index=True)

    class Meta:
        verbose_name = "Product"
        verbose_name_plural = "Products"
        ordering = ['product_name']
        unique_together = [['site', 'sku']]

    def __str__(self):
        return self.product_name


class ProductComponent(models.Model):
    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE, 
        related_name='components'
    )
    category = models.ForeignKey(
        'inventory.StockCategory', 
        on_delete=models.CASCADE, 
        verbose_name="Category"
    )
    sub_category = ChainedForeignKey(
        'inventory.StockSubCategory',
        chained_field="category",
        chained_model_field="category",
        show_all=False,
        auto_choose=True,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Sub Category"
    )
    stock_item = ChainedForeignKey(
        'inventory.StockItem', 
        chained_field="sub_category", 
        chained_model_field="sub_category", 
        show_all=False, 
        auto_choose=True, 
        sort=True, 
        verbose_name="Stock Item"
    )
    usage_per_pallet = models.DecimalField( 
        max_digits=12,
        decimal_places=4,
        default=1,
        verbose_name="Usage per Pallet"
    )
    standard_usage_per_production_unit = models.DecimalField(
        max_digits=12, 
        decimal_places=4, 
        default=1, 
        verbose_name="Usage per unit"
    )
    unit_of_measure = models.ForeignKey(
        'inventory.UnitOfMeasure', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Unit of Measure"
    )
    is_primary_packaging = models.BooleanField(
        default=False,
        verbose_name="Primary"
    )
    is_secondary_packaging = models.BooleanField(
        default=False,
        verbose_name="Secondary"
    )
    is_pallet = models.BooleanField(
        default=False,
        verbose_name="Pallet"
    )
    main_stock_item = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        related_name='secondary_stock_items',
        null=True,
        blank=True,
        verbose_name="Main Stock Item"
    )
    
    @staticmethod
    def get_packaging_info(product):
        """
        Dynamically fetch primary, secondary, and pallet info for a product
        Returns: {
            'primary': {'name': 'Pouches', 'usage_per_pallet': 990},
            'secondary': {'name': 'Rich Gravy Box', 'usage_per_pallet': 165},
            'pallet': {'name': 'Pallet', 'usage_per_pallet': 1}
        }
        """
        info = {
            'primary': None,
            'secondary': None,
            'pallet': None
        }
        
        primary = ProductComponent.objects.filter(
            product=product,
            is_primary_packaging=True
        ).first()
        if primary:
            info['primary'] = {
                'name': str(primary.stock_item),
                'usage_per_pallet': float(primary.usage_per_pallet)
            }
        
        secondary = ProductComponent.objects.filter(
            product=product,
            is_secondary_packaging=True
        ).first()
        if secondary:
            info['secondary'] = {
                'name': str(secondary.stock_item),
                'usage_per_pallet': float(secondary.usage_per_pallet)
            }
        
        pallet = ProductComponent.objects.filter(
            product=product,
            is_pallet=True
        ).first()
        if pallet:
            info['pallet'] = {
                'name': str(pallet.stock_item),
                'usage_per_pallet': float(pallet.usage_per_pallet)
            }
        
        return info
    
    class Meta:
        verbose_name = "Product Component"
        verbose_name_plural = "Product Components"
        ordering = ['product', 'category']

    def save(self, *args, **kwargs):
        if self.stock_item and self.stock_item.unit_of_measure:
            self.unit_of_measure = self.stock_item.unit_of_measure
        
        if self.is_primary_packaging:
            self.standard_usage_per_production_unit = 1
        
        if self.is_secondary_packaging:
            primary = ProductComponent.objects.filter(
                product=self.product,
                is_primary_packaging=True
            ).first()
            if primary and self.usage_per_pallet and primary.usage_per_pallet:
                ratio = primary.usage_per_pallet / self.usage_per_pallet
                self.standard_usage_per_production_unit = primary.standard_usage_per_production_unit / ratio
        
        if self.is_pallet:
            primary = ProductComponent.objects.filter(
                product=self.product,
                is_primary_packaging=True
            ).first()
            if primary and primary.usage_per_pallet:
                self.usage_per_pallet = 1
                self.standard_usage_per_production_unit = 1 / primary.usage_per_pallet
        
        if not self.is_primary_packaging and not self.is_secondary_packaging and not self.is_pallet:
            primary = ProductComponent.objects.filter(
                product=self.product,
                is_primary_packaging=True
            ).first()
            if primary and self.usage_per_pallet:
                self.standard_usage_per_production_unit = (
                    self.usage_per_pallet / primary.usage_per_pallet
                )
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product} - {self.stock_item}"

    def unit_display(self):
        if self.unit_of_measure:
            return self.unit_of_measure.abbreviation or self.unit_of_measure.name
        return "-"
    unit_display.short_description = "Unit of Measure"

class MainProductComponent(models.Model):
    """Direct stock items added to a product"""
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='main_product_components'
    )
    category = models.ForeignKey(
        'inventory.StockCategory',
        on_delete=models.CASCADE,
        verbose_name="Category"
    )
    sub_category = ChainedForeignKey(
        'inventory.StockSubCategory',
        chained_field="category",
        chained_model_field="category",
        show_all=False,
        auto_choose=True,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Sub Category"
    )
    stock_item = ChainedForeignKey(
        'inventory.StockItem',
        chained_field="sub_category",
        chained_model_field="sub_category",
        show_all=False,
        auto_choose=True,
        sort=True,
        verbose_name="Stock Item"
    )
    standard_usage_per_production_unit = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=1,
        verbose_name="Standard usage per production unit"
    )
    unit_of_measure = models.ForeignKey(
        'inventory.UnitOfMeasure',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Unit of Measure"
    )

    class Meta:
        verbose_name = "Main Product Component"
        verbose_name_plural = "Main Product Components"
        ordering = ['product', 'id']

    def save(self, *args, **kwargs):
        if self.stock_item and self.stock_item.unit_of_measure:
            self.unit_of_measure = self.stock_item.unit_of_measure
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product} - {self.stock_item}"

    def unit_display(self):
        if self.unit_of_measure:
            return self.unit_of_measure.abbreviation or self.unit_of_measure.name
        return "-"
    unit_display.short_description = "Unit of Measure"
    
class RecipeCategory(models.Model):
    """Top-level recipe category (e.g., Sauce, Spices, Concentrate)"""
    name = models.CharField(max_length=255)
    site = models.ForeignKey(
        'tenants.Site',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Site"
    )
    
    class Meta:
        verbose_name = "Recipe Category"
        verbose_name_plural = "Recipe Categories"
        ordering = ['name']
        unique_together = [['name', 'site']]
    
    def __str__(self):
        return self.name


class ProductRecipe(models.Model):
    """Recipe linked to product via RecipeCategory and recipe_name"""
    MEASURE_UNIT_CHOICES = [
        ('L', 'Litres (L)'),
        ('Kg', 'Kilograms (Kg)'),
    ]
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='recipes'
    )
    recipe_category = models.ForeignKey(
        RecipeCategory,
        on_delete=models.CASCADE,  
        verbose_name="Recipe Category"
    )
    recipe_name = models.CharField(
        max_length=255,
        verbose_name="Recipe Name",
        help_text="Enter the recipe name (e.g., Brown Sauce, Cream Sauce)"
    )
    standard_usage_per_production_unit = models.DecimalField(
        max_digits=12, 
        decimal_places=4, 
        default=1, 
        verbose_name="Usage per unit"
    )
    measure_unit = models.CharField(
        max_length=10,
        choices=MEASURE_UNIT_CHOICES,
        default='L',
        verbose_name="Measure Unit"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Product Recipe"
        verbose_name_plural = "Product Recipes"
        ordering = ['product', 'recipe_name']
        unique_together = ('product', 'recipe_category', 'recipe_name')

    def __str__(self):
        return f"{self.product.product_name} - {self.recipe_name}"

class ProductRecipeItem(models.Model):
    """Individual stock items within a recipe"""
    recipe = models.ForeignKey(
        ProductRecipe,
        on_delete=models.CASCADE,
        related_name='items'
    )
    category = models.ForeignKey(
        'inventory.StockCategory',
        on_delete=models.CASCADE,
        verbose_name="Category"
    )
    sub_category = ChainedForeignKey(
        'inventory.StockSubCategory',
        chained_field="category",
        chained_model_field="category",
        show_all=False,
        auto_choose=True,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Sub Category"
    )
    stock_item = ChainedForeignKey(
        'inventory.StockItem',
        chained_field="sub_category",
        chained_model_field="sub_category",
        show_all=False,
        auto_choose=True,
        sort=True,
        verbose_name="Stock Item"
    )
    standard_usage_per_production_unit = models.DecimalField(
        max_digits=12, 
        decimal_places=4, 
        default=1, 
        verbose_name="Usage per unit"
    )
    unit_of_measure = models.ForeignKey(
        'inventory.UnitOfMeasure',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Unit of Measure"
    )

    class Meta:
        verbose_name = "Recipe Item"
        verbose_name_plural = "Recipe Items"
        ordering = ['recipe', 'id']

    def save(self, *args, **kwargs):
        if self.stock_item and self.stock_item.unit_of_measure:
            self.unit_of_measure = self.stock_item.unit_of_measure
        super().save(*args, **kwargs)

    def __str__(self):
        recipe_name = self.recipe.recipe_name if self.recipe else "No Recipe"
        stock_name = str(self.stock_item) if self.stock_item else "No Stock Item"
        return f"{recipe_name} - {stock_name}"

    def unit_display(self):
        if self.unit_of_measure:
            return self.unit_of_measure.abbreviation or self.unit_of_measure.name
        return "-"
    unit_display.short_description = "Unit of Measure"
    
        