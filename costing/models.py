from django.db import models
from decimal import Decimal, InvalidOperation
from smart_selects.db_fields import ChainedForeignKey
from django.utils.safestring import mark_safe
from manufacturing.models import Batch
from django.db.models import Sum
from django.utils import timezone
from commercial.models import Client, CompanyDetails

class OverheadCosting(models.Model):
    site = models.ForeignKey(
        'tenants.Site',
        on_delete=models.CASCADE,
        related_name='overhead_costings',
        null=True,
        blank=True,
        help_text="Site this costing belongs to"
    )
    date = models.DateField(verbose_name="Date")
    description = models.CharField(max_length=200, verbose_name="Description")
    production_units = models.PositiveIntegerField(default=0, verbose_name="Production Units (Month)")
    
    is_archived = models.BooleanField(default=False, db_index=True)
    
    use_as_default = models.BooleanField(
        default=False,
        verbose_name="Use as Default",
        help_text="Mark this record as the default overhead costing to use"
    )
    @classmethod
    def get_default(cls):
        """Return the current default overhead costing, if any."""
        return cls.objects.filter(use_as_default=True).order_by('-date').first()
    @property
    def fixed_subtotal(self):
        return sum(item.per_month for item in self.items.filter(item_type='Fixed'))

    @property
    def variable_subtotal(self):
        return sum(item.per_month for item in self.items.filter(item_type='Variable'))

    @property
    def grand_total(self):
        return self.fixed_subtotal + self.variable_subtotal

    @property
    def price_per_unit(self):
        return (self.grand_total / self.production_units) if self.production_units else Decimal('0.00')

    class Meta:
        verbose_name = "Overhead Costing"
        verbose_name_plural = "Overhead Costing"
        ordering = ['-date']

    def __str__(self):
        return self.description 

class OverheadItem(models.Model):
    TYPE_CHOICES = [('Fixed', 'Fixed'), ('Variable', 'Variable')]
    header = models.ForeignKey(OverheadCosting, on_delete=models.CASCADE, related_name='items')
    item_name = models.CharField(max_length=100, verbose_name="Overhead Item")
    item_type = models.CharField(max_length=10, choices=TYPE_CHOICES, verbose_name="Type")
    per_month = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Per Month")

    @property
    def per_unit(self):
        units = self.header.production_units or 0
        if units <= 0:
            return Decimal('0')
        return self.per_month / units

    @property
    def per_week(self):
        return self.per_month / Decimal('4.333')

    @property
    def per_day(self):
        return self.per_month / 30

    @property
    def per_hour(self):
        return self.per_day / 8

    @property
    def percentage(self):
        total = self.header.grand_total
        return (self.per_month / total * 100) if total > 0 else 0

    class Meta:
        verbose_name = "Overhead Item"
        verbose_name_plural = "Overhead Items"
        ordering = ['item_type', 'item_name']

    def __str__(self):
        return f"{self.item_name} ({self.item_type}) - R{self.per_month:,.2f}"

class SalaryCosting(models.Model):
    site = models.ForeignKey(
        'tenants.Site',
        on_delete=models.CASCADE,
        related_name='salary_costings',
        null=True,
        blank=True,
        help_text="Site this costing belongs to"
    )
    date = models.DateField(verbose_name="Date")
    description = models.CharField(max_length=200, verbose_name="Description")
    management_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Management")
    office_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Office")
    production_units = models.PositiveIntegerField(default=0, verbose_name="Production Units (Month)")
    percentage_bonus = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="% Bonus")
    production_months = models.PositiveIntegerField(default=12, verbose_name="Production Months")
    is_archived = models.BooleanField(default=False, db_index=True)
    use_as_default = models.BooleanField(
        default=False,
        verbose_name="Use as Default",
        help_text="Mark this record as the default salary costing to use"
    )
    @classmethod
    def get_default(cls):
        """Return the current default overhead costing, if any."""
        return cls.objects.filter(use_as_default=True).order_by('-date').first()
    @property
    def fixed_subtotal(self):
        return self.management_salary + self.office_salary

    @property
    def production_subtotal(self):
        return sum(pos.total_per_month for pos in self.positions.all())

    @property
    def grand_total(self):
        return self.fixed_subtotal + self.production_subtotal

    @property
    def price_per_unit(self):
        if not self.production_units:
            return Decimal('0.00')
        
        base_price = self.grand_total / self.production_units
        
        # Apply bonus calculation if percentage_bonus and production_months are set
        if self.percentage_bonus and self.production_months:
            bonus_multiplier = self.percentage_bonus / Decimal('100')
            bonus_addition = (base_price * bonus_multiplier) / self.production_months
            return base_price + bonus_addition
        
        return base_price

    class Meta:
        verbose_name = "Salary Costing"
        verbose_name_plural = "Salary Costing"
        ordering = ['-date']

    def __str__(self):
        return self.description 
     
class SalaryPosition(models.Model):
    header = models.ForeignKey(SalaryCosting, on_delete=models.CASCADE, related_name='positions')
    position_name = models.CharField(max_length=100, verbose_name="Position Name")
    description = models.CharField(max_length=200, blank=True, verbose_name="Description")
    general_workers = models.IntegerField(default=0, verbose_name="General Workers")
    rate_per_hour = models.DecimalField(max_digits=8, decimal_places=2, default=25, verbose_name="Rate/Hour")
    qa_workers = models.IntegerField(default=0, verbose_name="QA Workers")
    qa_rate_per_hour = models.DecimalField(max_digits=8, decimal_places=2, default=50, verbose_name="QA Rate/Hour")
    shifts = models.IntegerField(default=1, verbose_name="Shifts per Day")
    shift_hours = models.DecimalField(max_digits=4, decimal_places=1, default=8, verbose_name="Hours per Shift")
    days_worked = models.DecimalField(max_digits=4, decimal_places=1, default=20, verbose_name="Days Worked")

    @property
    def total_per_hour(self):
        return (self.general_workers * self.rate_per_hour) + (self.qa_workers * self.qa_rate_per_hour)

    @property
    def total_per_day(self):
        return self.total_per_hour * self.shifts * self.shift_hours

    @property
    def total_per_month(self):
        # CORRECTED: Hours per Shift × Per Hour × Days Worked
        return self.shift_hours * self.total_per_hour * self.days_worked

    @property
    def percentage(self):
        total = self.header.grand_total
        return (self.total_per_month / total * 100) if total > 0 else 0

    class Meta:
        verbose_name = "Salary Position"
        verbose_name_plural = "Salary Positions"
        ordering = ['position_name']

    def __str__(self):
        return f"{self.position_name} - R{self.total_per_month:,.2f}/month"

class BatchCosting(models.Model):
    """Batch Costing linked to Production Date - pulls all data from Production system"""
    site = models.ForeignKey(
        'tenants.Site',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='batch_costings'
    )
    production_date = models.OneToOneField(
        'manufacturing.Production',
        on_delete=models.CASCADE,
        related_name='batch_costing',
        verbose_name="Production Date",
        null=True,
        blank=True
    )
    overhead_costing = models.ForeignKey(
        OverheadCosting,
        on_delete=models.SET_NULL,
        verbose_name="Overhead Costing",
        null=True,
        blank=True
    )
    salary_costing = models.ForeignKey(
        SalaryCosting,
        on_delete=models.SET_NULL,
        verbose_name="Salary Costing",
        null=True,
        blank=True
    )
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Selling Price",
        help_text="Selling Price = stock price incl VAT + overhead per unit + salary per unit + markup.",
    )
    use_markup = models.BooleanField(
        default=False,
        verbose_name="Use Markup %",
        help_text="Check to apply percentage markup"
    )
    markup_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name="Markup %"
    )
    use_markup_per_unit = models.BooleanField(   
        default=True,
        verbose_name="Use Markup per Unit",
        help_text="Check to apply fixed markup"
    )
    markup_per_unit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Markup per Unit"
    )
    stock_item_price_use = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Stock Item Price Use",
        help_text="Price to use for costing calculations"
    )
    # Snapshot fields - preserve costing values at time of first save
    overhead_price_per_unit_snapshot = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name="Overhead Price/Unit (Snapshot)",
        help_text="Captured overhead price per unit at time of first save. Won't change if default overhead is updated."
    )
    salary_price_per_unit_snapshot = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name="Salary Price/Unit (Snapshot)",
        help_text="Captured salary price per unit at time of first save. Won't change if default salary is updated."
    )
    date_created = models.DateField(auto_now_add=True, verbose_name="Date Created")
    notes = models.TextField(blank=True, null=True, help_text="Additional notes about this batch costing")
    is_archived = models.BooleanField(default=False, db_index=True)
    # ===== READ-ONLY DATA AGGREGATION =====

    @property
    def batches(self):
        """Get all batches for this production date"""
        if not self.production_date:
            return []
        return self.production_date.batch_items.all()

    @property
    def total_batches(self):
        """Total number of batches"""
        return self.batches.count()

    @property
    def total_shift_total(self):
        """Total shift_total across all batches"""
        result = self.production_date.batch_items.aggregate(total=Sum('shift_total')) if self.production_date else {}
        return result.get('total') or 0

    # ===== INVENTORY & STOCK TRANSACTION COSTING =====

    @property
    def inventory_items(self):
        """Get all inventory items used for this production date's batches"""
        from manufacturing.models import BatchProductInventoryUsed
        batch_ids = list(self.batches.values_list('batch_number', flat=True))
        if not batch_ids:
            return BatchProductInventoryUsed.objects.none()
        return BatchProductInventoryUsed.objects.filter(
            batch__batch_number__in=batch_ids
        ).select_related('stock_item', 'batch')

    @property
    def stock_transactions(self):
        """Get all OUT transactions for this production date"""
        from inventory.models import StockTransaction
        if not self.production_date:
            return StockTransaction.objects.none()
        return StockTransaction.objects.filter(
            transaction_date=self.production_date.production_date,
            transaction_type='OUT'
        ).select_related('stock_item')

    @property
    def total_stock_value_used(self):
        """Total value of stock used (quantity × unit cost)"""
        total = Decimal('0.00')
        for trans in self.stock_transactions:
            qty = Decimal(str(trans.quantity or 0))
            cost = Decimal(str(trans.stock_item.standard_cost_incl_transport or 0))
            total += qty * cost
        return total

    @property
    def cost_per_unit_inventory(self):
        """Inventory cost per unit"""
        if self.total_shift_total > 0:
            return self.total_stock_value_used / Decimal(str(self.total_shift_total))
        return Decimal('0.00')

    # ===== COSTING TOTALS =====
    # Note: overhead_price_per_unit and salary_price_per_unit are defined near the save() method
    # to support snapshot functionality for historical record preservation

    @property
    def total_cost_per_unit(self):
        """COMPLETE cost per unit = Inventory + Overhead + Salary"""
        return (
            self.cost_per_unit_inventory +
            self.overhead_price_per_unit +
            self.salary_price_per_unit
        )

    @property
    def total_production_cost(self):
        """Total cost for entire production"""
        return self.total_cost_per_unit * Decimal(str(self.total_shift_total))

    @property
    def summary_items(self):
        """
        Get summary items by querying same sources as Manufacturing Summary.
        Calculate dynamically: IDEAL = pouches × standard_usage
        No database persistence - calculated on-demand
        """
        if not self.production_date:
            return []
        
        production_date = self.production_date.production_date
        batch = self.production_date.batch_items.first()
        
        if not batch or not batch.product:
            return []
        
        product = batch.product
        
        # Get total pouches
        from manufacturing.models import Batch
        total_pouches = Batch.objects.filter(
            production_date=production_date
        ).aggregate(total=Sum('shift_total'))['total'] or 0
        
        if not total_pouches:
            return []
        
        total_pouches = Decimal(str(total_pouches))
        items_list = []
        
        # ============= 1. MAIN PRODUCT COMPONENTS =============
        for comp in product.main_product_components.all():
            standard_usage = Decimal(str(comp.standard_usage_per_production_unit or 0))
            ideal = total_pouches * standard_usage
            
            from manufacturing.models import BatchProductInventoryUsed
            batch_usage = BatchProductInventoryUsed.objects.filter(
                batch__production_date=production_date,
                stock_item=comp.stock_item
            ).first()
            
            used = Decimal(str(batch_usage.qty_used or 0)) if batch_usage else Decimal('0')
            batch_ref = batch_usage.ref_number if batch_usage else ""
            
            items_list.append({
                'stock_item_id': comp.stock_item.id,
                'stock_item_name': comp.stock_item.name,
                'unit': comp.unit_of_measure.abbreviation if comp.unit_of_measure and comp.unit_of_measure.abbreviation else (comp.unit_of_measure.name if comp.unit_of_measure else 'Unit'),
                'component_type': 'main',
                'ideal': float(ideal),
                'used': float(used),
                'difference': float(ideal - used),
                'batch_ref': batch_ref,
            })
        
        # ============= 2. PRODUCT COMPONENTS =============
        for comp in product.components.all():
            standard_usage = Decimal(str(comp.standard_usage_per_production_unit or 0))
            ideal = total_pouches * standard_usage
            
            batch_usage = BatchProductInventoryUsed.objects.filter(
                batch__production_date=production_date,
                stock_item=comp.stock_item
            ).first()
            
            used = Decimal(str(batch_usage.qty_used or 0)) if batch_usage else Decimal('0')
            batch_ref = batch_usage.ref_number if batch_usage else ""
            
            items_list.append({
                'stock_item_id': comp.stock_item.id,
                'stock_item_name': comp.stock_item.name,
                'unit': comp.unit_of_measure.abbreviation if comp.unit_of_measure and comp.unit_of_measure.abbreviation else (comp.unit_of_measure.name if comp.unit_of_measure else 'Unit'),
                'component_type': 'component',
                'ideal': float(ideal),
                'used': float(used),
                'difference': float(ideal - used),
                'batch_ref': batch_ref,
            })
        
        # ============= 3. RECIPE ITEMS =============
        for recipe in product.recipes.all():
            for recipe_item in recipe.items.all():
                standard_usage = Decimal(str(recipe_item.standard_usage_per_production_unit or 0))
                ideal = total_pouches * standard_usage
                
                batch_usage = BatchProductInventoryUsed.objects.filter(
                    batch__production_date=production_date,
                    stock_item=recipe_item.stock_item
                ).first()
                
                used = Decimal(str(batch_usage.qty_used or 0)) if batch_usage else Decimal('0')
                batch_ref = batch_usage.ref_number if batch_usage else ""
                
                items_list.append({
                    'stock_item_id': recipe_item.stock_item.id,
                    'stock_item_name': recipe_item.stock_item.name,
                    'unit': recipe_item.unit_of_measure.abbreviation if recipe_item.unit_of_measure and recipe_item.unit_of_measure.abbreviation else (recipe_item.unit_of_measure.name if recipe_item.unit_of_measure else 'Unit'),
                    'component_type': 'recipe',
                    'ideal': float(ideal),
                    'used': float(used),
                    'difference': float(ideal - used),
                    'batch_ref': batch_ref,
                })
        
        return items_list

    def get_summary_items_html(self):
        """Generate HTML table for summary items - READ-ONLY"""
        items = self.summary_items
        
        if not items:
            return mark_safe(
                "<div style='padding: 15px; background-color: #f0f0f0; border-radius: 4px; color: #999;'>"
                "<p>⏳ No summary items available yet. Run manufacturing batch saves first.</p>"
                "</div>"
            )
        
        rows = []
        total_ideal = total_used = total_difference = 0
        
        for item in items:
            total_ideal += item['ideal']
            total_used += item['used']
            total_difference += item['difference']
            
            row_color = '#fff3cd' if item['difference'] < 0 else '#ffffff'
            diff_color = '#d32f2f' if item['difference'] < 0 else '#4caf50'
            
            rows.append(f"""<tr style="background-color: {row_color}; border-bottom: 1px solid #ddd;">
                <td style="border-right: 1px solid #ddd; padding: 10px; font-weight: 500; font-size: 12px;">{item['stock_item_name']}</td>
                <td style="border-right: 1px solid #ddd; padding: 10px; text-align: center; font-size: 12px;">{item['unit']}</td>
                <td style="border-right: 1px solid #ddd; padding: 10px; text-align: right; background-color: #e3f2fd; font-size: 12px;">
                    <strong>{item['ideal']:,.2f}</strong></td>
                <td style="border-right: 1px solid #ddd; padding: 10px; text-align: right; background-color: #f3e5f5; font-size: 12px;">
                    <strong>{item['used']:,.2f}</strong></td>
                <td style="border-right: 1px solid #ddd; padding: 10px; text-align: right; font-size: 12px;">
                    <strong style="color: {diff_color};">{item['difference']:+,.2f}</strong></td>
                <td style="padding: 10px; text-align: left; font-size: 11px; max-width: 150px; word-break: break-word;">{item['batch_ref']}</td>
            </tr>""")
        
        html = f"""<table style="width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 10px; margin-bottom: 15px;">
            <thead><tr style="background-color: #1976d2; color: white; font-weight: bold;">
                <th style="border-right: 1px solid #ddd; padding: 10px; text-align: left;">Item</th>
                <th style="border-right: 1px solid #ddd; padding: 10px; text-align: center;">Unit</th>
                <th style="border-right: 1px solid #ddd; padding: 10px; text-align: center;">Ideal</th>
                <th style="border-right: 1px solid #ddd; padding: 10px; text-align: center;">Used</th>
                <th style="border-right: 1px solid #ddd; padding: 10px; text-align: center;">Difference</th>
                <th style="padding: 10px; text-align: center;">Batch Ref</th>
            </tr></thead>
            <tbody>{''.join(rows)}</tbody>
            <tfoot>
                <tr style="background-color: #f5f5f5; border-top: 2px solid #1976d2; font-weight: bold;">
                    <td colspan="2" style="padding: 10px; text-align: right;">TOTALS:</td>
                    <td style="border-right: 1px solid #ddd; padding: 10px; text-align: right; background-color: #e3f2fd;">
                        {total_ideal:,.2f}</td>
                    <td style="border-right: 1px solid #ddd; padding: 10px; text-align: right; background-color: #f3e5f5;">
                        {total_used:,.2f}</td>
                    <td style="border-right: 1px solid #ddd; padding: 10px; text-align: right; color: #d32f2f;">
                        {total_difference:+,.2f}</td>
                    <td style="padding: 10px;"></td>
                </tr>
            </tfoot>
        </table>"""
        
        return mark_safe(html)

    def save(self, *args, **kwargs):
        """Save BatchCosting and handle markup calculations.
        
        Snapshot Logic:
        - On first save (or if snapshot is None), capture the current overhead/salary price per unit
        - On subsequent saves, preserve the existing snapshot (don't update it)
        - This ensures historical records aren't affected when default costing changes
        """
        # Capture overhead snapshot on first save or if never set
        if self.overhead_price_per_unit_snapshot is None and self.overhead_costing:
            self.overhead_price_per_unit_snapshot = self.overhead_costing.price_per_unit
        
        # Capture salary snapshot on first save or if never set
        if self.salary_price_per_unit_snapshot is None and self.salary_costing:
            self.salary_price_per_unit_snapshot = self.salary_costing.price_per_unit
        
        # Handle markup calculations
        if self.use_markup and self.markup_percentage:
            self.markup_per_unit = self.total_cost_per_unit * (Decimal(str(self.markup_percentage)) / Decimal('100'))
        elif self.use_markup_per_unit and self.markup_per_unit:
            pass  # Fixed markup per unit already set
        else:
            self.markup_per_unit = Decimal('0.00')
        
        super().save(*args, **kwargs)

    @property
    def overhead_price_per_unit(self):
        """Overhead cost per unit - use snapshot if available, otherwise live value"""
        if self.overhead_price_per_unit_snapshot is not None:
            return self.overhead_price_per_unit_snapshot
        return self.overhead_costing.price_per_unit if self.overhead_costing else Decimal('0.00')

    @property
    def salary_price_per_unit(self):
        """Salary cost per unit - use snapshot if available, otherwise live value"""
        if self.salary_price_per_unit_snapshot is not None:
            return self.salary_price_per_unit_snapshot
        return self.salary_costing.price_per_unit if self.salary_costing else Decimal('0.00')

    class Meta:
        verbose_name = "Batch Costing"
        verbose_name_plural = "Batch Costing"
        ordering = ['-production_date']

    def __str__(self):
        return f"Batch Costing - {self.production_date}"

class BatchPriceApproval(models.Model):
    batch_costing = models.ForeignKey(
        BatchCosting,
        on_delete=models.CASCADE,
        related_name='price_approvals',  # Changed plural
        verbose_name="Batch Costing"
    )
    batch = models.ForeignKey(  # ← ADD THIS
        Batch,
        on_delete=models.CASCADE,
        related_name='price_approval',
        verbose_name="Batch"
    )
    batch_price_per_unit = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=0,
        verbose_name="Batch Price per Unit"
    )
    is_approved = models.BooleanField(
        default=False,
        verbose_name="Approved"
    )
    date_created = models.DateField(auto_now_add=True)

    class Meta:
        verbose_name = "Batch Price Approval"
        verbose_name_plural = "Batch Price Approvals"
        unique_together = ('batch_costing', 'batch')  # ← Prevent duplicates

    def __str__(self):
        return f"{self.batch.batch_number} - R{self.batch_price_per_unit}"
        
class ProductCostingStockItem(models.Model):
    """Links stock items used in a product costing with price tracking"""
    product_costing = models.ForeignKey(
        'ProductCosting',
        on_delete=models.CASCADE,
        related_name='stock_items'
    )
    stock_item = models.ForeignKey(
        'inventory.StockItem',
        on_delete=models.CASCADE,
        verbose_name="Stock Item"
    )
    usage_per_unit = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        verbose_name="Usage"
    )
    unit_of_measure = models.CharField(
        max_length=10,
        verbose_name="Unit",
        editable=False
    )
    price_including_transport = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Price Inc Transport",
        editable=False
    )
    price_per_unit_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Price per Unit",
        editable=False
    )
    use_price_per_unit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Use Price per Unit",
        help_text="Editable price to use for costing (defaults to calculated price per unit)"
    )
    waste_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name="Waste %",
        help_text="Waste percentage for this item"
    )
    use_markup = models.BooleanField(
        default=False,
        verbose_name="Use Markup",
        help_text="Check to apply markup to this item"
    )
    markup_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name="% Markup",
        help_text="Markup percentage to apply"
    )
    markup_per_unit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Markup per Unit",
        editable=False,
        help_text="Calculated markup amount per unit"
    )

    def save(self, *args, **kwargs):
        if self.stock_item:
            # 1. Get unit from stock_item
            self.unit_of_measure = str(self.stock_item.unit_of_measure) if self.stock_item.unit_of_measure else ""
            
            # 2. Get price_including_transport from stock_item
            self.price_including_transport = self.stock_item.standard_cost_incl_transport or Decimal('0.00')
            
            # 3. Calculate price_per_unit = usage × price_including
            usage = Decimal(str(self.usage_per_unit)) if self.usage_per_unit else Decimal('0')
            price = Decimal(str(self.price_including_transport)) if self.price_including_transport else Decimal('0')
            self.price_per_unit_amount = usage * price
            
            # 4. Default use_price_per_unit to calculated price_per_unit if not set
            if not self.use_price_per_unit or self.use_price_per_unit == 0:
                self.use_price_per_unit = self.price_per_unit_amount
            
            # 5. Calculate markup_per_unit if markup enabled
            if self.use_markup and self.markup_percentage:
                self.markup_per_unit = self.use_price_per_unit * (Decimal(str(self.markup_percentage)) / Decimal('100'))
            else:
                self.markup_per_unit = Decimal('0.00')
        
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name = "Product Costing Stock Item"
        verbose_name_plural = "Product Costing Stock Items"
    
    def __str__(self):
        return f"{self.stock_item} - {self.usage_per_unit}"

class ProductCosting(models.Model):
    site = models.ForeignKey(
        'tenants.Site',
        on_delete=models.CASCADE,
        related_name='product_costings',
        null=True,
        blank=True,
        help_text="Site this product costing belongs to"
    )
    category = models.ForeignKey(
        'product_details.ProductCategory',
        on_delete=models.CASCADE,
        verbose_name="Category",
        null=True,
        blank=True
    )
    product = ChainedForeignKey(
        'product_details.Product',
        chained_field="category",
        chained_model_field="category",
        show_all=False,
        auto_choose=True,
        on_delete=models.CASCADE,
        verbose_name="Product"
    )
    overhead_costing = models.ForeignKey(
        OverheadCosting,
        on_delete=models.CASCADE,
        verbose_name="Overhead Costing",
        null=True,
        blank=True
    )
    salary_costing = models.ForeignKey(
        SalaryCosting,
        on_delete=models.CASCADE,
        verbose_name="Salary Costing",
        null=True,
        blank=True
    )
    use_markup = models.BooleanField(
        default=False,
        verbose_name="Use Markup %",
        help_text="Check to apply percentage markup"
    )
    markup_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name="Markup %"
    )
    use_markup_percentage = models.BooleanField(
        default=True,
        verbose_name="Use Markup per Unit",
        help_text="Check to apply fixed markup"
    )
    markup_per_unit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Markup per Unit"
    )
    waste_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name="Waste %",
        help_text="Global waste percentage"
    )
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Selling Price",
        help_text=(
            "Selling Price = Total stock items incl. VAT "
            "+ Overhead price per unit + Salary price per unit "
            "+ Markup (percentage or fixed per unit)."
        ),
    )
    # Snapshot fields - preserve costing values; for ProductCosting these can be updated via confirmation popup
    overhead_price_per_unit_snapshot = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name="Overhead Price/Unit (Snapshot)",
        help_text="Captured overhead price per unit. Can be updated via confirmation when default changes."
    )
    salary_price_per_unit_snapshot = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name="Salary Price/Unit (Snapshot)",
        help_text="Captured salary price per unit. Can be updated via confirmation when default changes."
    )
    date = models.DateField(auto_now_add=True, verbose_name="Date Created")
    notes = models.TextField(blank=True, null=True, help_text="Additional notes about this product costing")
    
    is_archived = models.BooleanField(default=False, db_index=True)
        
    @property
    def total_overhead(self):
        return self.overhead_costing.grand_total if self.overhead_costing else Decimal('0.00')

    @property
    def total_salary(self):
        return self.salary_costing.grand_total if self.salary_costing else Decimal('0.00')

    @property
    def grand_total(self):
        return self.total_overhead + self.total_salary
    
    @property
    def total_stock_items_excl_vat(self):
        """Total of (use_price_per_unit + waste %) for all items"""
        total = Decimal('0.00')
        for item in self.stock_items.all():
            # Calculate waste amount
            waste_amount = item.use_price_per_unit * (Decimal(str(item.waste_percentage)) / Decimal('100'))
            # Add use_price_per_unit + waste_amount
            item_total = item.use_price_per_unit + waste_amount
            total += item_total
        return total or Decimal('0.00')

    @property
    def total_stock_items_incl_vat(self):
        """Total stock items including 15% VAT"""
        subtotal = self.total_stock_items_excl_vat
        vat = subtotal * Decimal('0.15')
        return subtotal + vat

    @property
    def total_waste(self):
        """Total waste across all items"""
        total = Decimal('0.00')
        for item in self.stock_items.all():
            waste = item.use_price_per_unit * (Decimal(str(item.waste_percentage)) / Decimal('100'))
            total += waste
        return total

    @property
    def total_markup(self):
        """Total markup across all items"""
        return sum(
            item.markup_per_unit for item in self.stock_items.all()
        ) or Decimal('0.00')

    @property
    def overhead_price_per_unit(self):
        """Overhead cost per unit - use snapshot if available, otherwise live value"""
        if self.overhead_price_per_unit_snapshot is not None:
            return self.overhead_price_per_unit_snapshot
        return self.overhead_costing.price_per_unit if self.overhead_costing else Decimal('0.00')

    @property
    def salary_price_per_unit(self):
        """Salary cost per unit - use snapshot if available, otherwise live value"""
        if self.salary_price_per_unit_snapshot is not None:
            return self.salary_price_per_unit_snapshot
        return self.salary_costing.price_per_unit if self.salary_costing else Decimal('0.00')

    def save(self, *args, **kwargs):
        """Save ProductCosting with snapshot handling.
        
        For ProductCosting, snapshots work differently than BatchCosting:
        - User can choose to update snapshot when default changes (via popup)
        - The 'update_snapshots' flag in kwargs controls this behavior
        """
        update_snapshots = kwargs.pop('update_snapshots', False)
        
        # If update_snapshots is True, or if snapshot is None, capture the current values
        if update_snapshots or self.overhead_price_per_unit_snapshot is None:
            if self.overhead_costing:
                self.overhead_price_per_unit_snapshot = self.overhead_costing.price_per_unit
        
        if update_snapshots or self.salary_price_per_unit_snapshot is None:
            if self.salary_costing:
                self.salary_price_per_unit_snapshot = self.salary_costing.price_per_unit
        
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Product Costing"
        verbose_name_plural = "Product Costing"
        ordering = ['-date']

    def __str__(self):
        return f"{self.product}"

from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=BatchCosting)
def create_batch_price_approvals(sender, instance, created, **kwargs):
    """Auto-create BatchPriceApproval for each batch in production_date"""
    # Skip signal during loaddata (raw=True)
    if kwargs.get('raw', False):
        return
        
    if not instance.production_date:
        return
    
    # Get all batches for this production date
    batches = instance.production_date.batch_items.all()
    
    for batch in batches:
        # Create or get the approval record
        BatchPriceApproval.objects.get_or_create(
            batch_costing=instance,
            batch=batch,
            defaults={
                'batch_price_per_unit': 0,
                'is_approved': False,
            }
        )

class BillingDocumentHeader(models.Model):
    site = models.ForeignKey(
        'tenants.Site',
        on_delete=models.CASCADE,
        related_name='billing_documents',
        null=True,
        blank=True,
        help_text="Site this billing document belongs to"
    )
    
    # HQ Import fields - for tracking which site invoices were imported from
    import_source_site = models.ForeignKey(
        'tenants.Site',
        on_delete=models.SET_NULL,
        related_name='imported_billing_documents',
        null=True,
        blank=True,
        verbose_name="Source Site",
        help_text="The site this HQ import came from"
    )
    import_source_invoice_number = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Source Invoice Number",
        help_text="Original invoice number from the source site"
    )
    
    CURRENCY_CHOICES = [
        ("R", "R"),
        ("NAD", "NAD"),
        ("USD", "$"),
        ("EUR", "€"),
    ]
    
    batch_costings = models.ManyToManyField(
        BatchCosting,
        related_name='billing_headers_multi',
        blank=True,
        verbose_name="Product Costings (hidden)",
    )
    production_dates_text = models.TextField(
        blank=True, 
        default='', 
        help_text="Comma-separated production dates"
    )
    company = models.ForeignKey(                  
        CompanyDetails,
        on_delete=models.PROTECT,
        related_name="billing_headers",
        null=True,
        blank=True,
        verbose_name="Company",
    )
    client = models.ForeignKey(
        Client,
        on_delete=models.PROTECT,
        related_name='billing_headers',
        verbose_name="Client",
        null=True,
        blank=True,
    )
    delivery_institution = models.ForeignKey(
        'transport.DeliverySite',
        on_delete=models.SET_NULL,
        related_name='billing_headers',
        verbose_name="Delivery Institution",
        null=True,
        blank=True,
        help_text="Select the institution/location to deliver to for this client",
    )
    transporters = models.ForeignKey(
        'commercial.Transporter',
        on_delete=models.PROTECT,
        related_name='billing_headers',
        verbose_name="Transporter",
        null=True,
        blank=True,
    )
    base_number = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="Base Number",
    )
 
    bill_per_pallet = models.BooleanField("pallet", default=False)
    bill_per_secondary = models.BooleanField("secondary packaging", default=False)
    bill_per_primary = models.BooleanField("primary packaging", default=False)
    
    billing_date = models.DateField("Billing date", default=timezone.now)   
    due_date = models.DateField("Due date", null=True, blank=True)
    
    from_currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default="NAD",
        verbose_name="From currency",
    )
    to_currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default="R",
        verbose_name="To currency",
    )
    exchange_rate = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=1,
        verbose_name="Exchange rate",
        help_text="Rate from from-currency to to-currency.",
    )
    vat_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=15,
        verbose_name="VAT %",
        help_text="Value Added Tax percentage (default 15%)",
    )
    transport_cost = models.DecimalField(
        "Transport cost",
        max_digits=12,
        decimal_places=2,
        default=0,
    )
    
    create_quote = models.BooleanField(default=False, verbose_name="Create Quote")
    create_proforma = models.BooleanField(default=False, verbose_name="Create Proforma")
    create_invoice = models.BooleanField(default=True, verbose_name="Create Invoice")
    create_picking_slip = models.BooleanField(default=False, verbose_name="Create Picking Slip")
    create_delivery_note = models.BooleanField(default=False, verbose_name="Create Delivery Note")
    
    qty_for_invoice_data = models.JSONField(default=dict, blank=True)

    quote_created = models.BooleanField(default=False, editable=False)
    proforma_created = models.BooleanField(default=False, editable=False)
    invoice_created = models.BooleanField(default=False, editable=False)
    picking_slip_created = models.BooleanField(default=False, editable=False)
    delivery_note_created = models.BooleanField(default=False, editable=False)

    # HQ-specific: Mark as dispatched to trigger transport creation (replaces picking slip approval for HQ)
    dispatched = models.BooleanField(
        default=False,
        verbose_name="Dispatched"
    )

    date_created = models.DateField(auto_now_add=True)
    is_archived = models.BooleanField(default=False, db_index=True)
    class Meta:
        verbose_name = "Billing"
        verbose_name_plural = "Billing"
        ordering = ['-date_created']

    def __str__(self):
        # For imports, show import source info
        if self.import_source_site:
            return f"{self.base_number} - {self.client} (Import from {self.import_source_site.name} #{self.import_source_invoice_number})"
        
        # For regular site/HQ billing, show batch costings
        all_costings = self.get_all_batch_costings()
        costings_str = ", ".join([str(c) for c in all_costings]) if all_costings else "Direct Billing"
        return f"{self.base_number} - {self.client} ({costings_str})"

    def get_document_type(self):
        if self.create_invoice:
            return "Invoice"
        if self.create_quote:
            return "Quote"
        if self.create_proforma:
            return "Proforma"
        if self.create_picking_slip:
            return "Picking Slip"
        if self.create_delivery_note:
            return "Delivery Note"
        return "Billing Document"

    def get_all_batch_costings(self):
        """Get from M2M field"""
        return list(self.batch_costings.all())
    
    def clean(self):
        '''Validate qty_for_invoice_data against available stock'''
        from django.core.exceptions import ValidationError
        from manufacturing.models import Batch
        from decimal import Decimal
        
        super().clean()
        
        # Skip validation for HQ imports - batches exist in source site, not HQ
        if self.import_source_site:
            return
        
        if self.qty_for_invoice_data:
            errors = {}
            
            for batch_number, qty in self.qty_for_invoice_data.items():
                
                if qty is None or qty == '' or qty == 'null':
                    continue
                
                try:
                    qty_decimal = Decimal(str(qty))
                    
                    if qty_decimal <= 0:
                        continue
                    
                    batch = Batch.objects.get(batch_number=batch_number)

                    from inventory.models import FinishedProductTransaction
                    from django.db.models import Sum

                    in_tx = FinishedProductTransaction.objects.filter(
                        batch=batch,
                        transaction_type='IN'
                    ).order_by('pk').first()

                    if not in_tx or not in_tx.ready_to_dispatch:
                        available = Decimal('0')
                    else:
                        starting_qty = Decimal(str(in_tx.ready_to_dispatch))
                        
                        # EXCLUDE this billing's own dispatches when editing
                        released_filter = FinishedProductTransaction.objects.filter(
                            batch=batch,
                            transaction_type='DISPATCH',
                            status='RELEASED'
                        )
                        
                        # If editing (self.pk exists), exclude this billing's dispatches
                        if self.pk:
                            released_filter = released_filter.exclude(
                                notes__contains=f"Billing {self.base_number}"
                            )
                        
                        released_dispatched = released_filter.aggregate(
                            total=Sum('quantity')
                        )['total'] or Decimal('0')
                        
                        scrapped = FinishedProductTransaction.objects.filter(
                            batch=batch,
                            transaction_type='SCRAP'
                        ).aggregate(total=Sum('quantity'))['total'] or Decimal('0')
                        
                        available = starting_qty - released_dispatched - scrapped
                    
                    if qty_decimal > available:
                        errors[batch_number] = (
                            f"Only {available} available, requested {qty}"
                        )
                
                except (ValueError, TypeError, InvalidOperation):
                    errors[batch_number] = f"Invalid quantity: {qty}"
                except Batch.DoesNotExist:
                    errors[batch_number] = "Batch not found"
            
            if errors:
                combined = "; ".join(
                    f"{batch_number}: {msg}"
                    for batch_number, msg in errors.items()
                )
                raise ValidationError({
                    'qty_for_invoice_data': combined
                })

    def save(self, *args, **kwargs):
        """Model save - handles dispatch creation"""
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # Skip dispatch creation for HQ imports - no actual stock movement
        if self.import_source_site:
            return
        
        # Create PENDING dispatches when Proforma or Invoice is selected
        if (self.create_proforma or self.create_invoice):
            self._create_pending_dispatches()
        
        # Auto-generate and attach picking slip when checkbox is checked
        if self.create_picking_slip:
            self._generate_and_attach_picking_slip()

    def _generate_and_attach_picking_slip(self):
        """
        DISABLED: Picking slip generation moved to manual workflow
        """
        return
        
    def _create_pending_dispatches(self):
        """Create or UPDATE dispatch transactions for this billing."""
        from inventory.models import FinishedProductTransaction
        from django.utils import timezone
        from decimal import Decimal
        
        # ✅ Get ALL batch_costings (M2M)
        batch_costings = self.batch_costings.all()
        
        if not batch_costings.exists():
            return
        
        # ✅ Loop through each batch_costing
        for batch_costing in batch_costings:
            if not batch_costing.production_date:
                continue
            
            batches = batch_costing.production_date.batch_items.all()
            
            for batch in batches:
                batch_number = batch.batch_number
                qty = self.qty_for_invoice_data.get(batch_number)
                
                if not qty:
                    continue
                
                try:
                    qty_decimal = Decimal(str(qty))
                    
                    if qty_decimal <= 0:
                        continue
                    
                    # Get warehouse from Book In
                    book_in_transaction = FinishedProductTransaction.objects.filter(
                        batch=batch,
                        transaction_type='IN'
                    ).order_by('pk').first()
                    
                    warehouse = book_in_transaction.to_warehouse if book_in_transaction else None
                    
                    # Check if dispatch ALREADY EXISTS for THIS billing + batch
                    existing_dispatch = FinishedProductTransaction.objects.filter(
                        batch=batch,
                        transaction_type='DISPATCH',
                        notes__contains=f"Billing {self.base_number}"
                    ).first()
                    
                    if existing_dispatch:
                        # UPDATE existing dispatch
                        existing_dispatch.quantity = qty_decimal
                        existing_dispatch.from_warehouse = warehouse
                        existing_dispatch.client = self.client
                        existing_dispatch.save()
                    else:
                        # CREATE new dispatch
                        FinishedProductTransaction.objects.create(
                            batch=batch,
                            transaction_type='DISPATCH',
                            quantity=qty_decimal,
                            client=self.client,
                            date=self.billing_date or timezone.now().date(),
                            product_name=batch.product.product_name if batch.product else '',
                            size=getattr(batch, 'size', ''),
                            from_warehouse=warehouse,
                            stock_released=False,
                            status='PENDING',
                            stock_released_date=None,
                            notes=f"Billing {self.base_number}",
                        )
                except (ValueError, TypeError, Exception):
                    continue


class BillingLineItem(models.Model):
    """Line items for HQ billing - stores batch quantities and pricing"""
    billing_document = models.ForeignKey(
        BillingDocumentHeader,
        on_delete=models.CASCADE,
        related_name='line_items',
        verbose_name="Billing Document"
    )
    site = models.ForeignKey(
        'tenants.Site',
        on_delete=models.PROTECT,
        related_name='billing_line_items',
        verbose_name="Site",
        null=True,
        blank=True,
        help_text="Filter batches by site"
    )
    batch = models.ForeignKey(
        'manufacturing.Batch',
        on_delete=models.PROTECT,
        related_name='billing_line_items',
        verbose_name="Batch"
    )
    qty_for_invoice = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Qty for Invoice"
    )
    selling_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Selling Price",
        help_text="Price per unit"
    )
    
    class Meta:
        verbose_name = "Billing Line Item"
        verbose_name_plural = "Billing Line Items"
        unique_together = ['billing_document', 'batch']
    
    def __str__(self):
        return f"{self.batch} - Qty: {self.qty_for_invoice}"
    
    @property
    def product(self):
        """Get product name from batch"""
        return self.batch.product.product_name if self.batch and self.batch.product else '-'
    
    @property
    def size(self):
        """Get size from batch"""
        return self.batch.size if self.batch else '-'
    
    @property
    def line_total(self):
        """Calculate line total"""
        return self.qty_for_invoice * self.selling_price

