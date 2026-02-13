from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.conf import settings
from compliance.models import (
    PolicyCategory,
    PolicyComplianceDocument,
    SopsCategory,
    SopsComplianceDocument,
)

from smart_selects.db_fields import ChainedForeignKey

class Department(models.Model):
    site = models.ForeignKey(
        'tenants.Site',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='departments'
    )
    name = models.CharField(max_length=50)

    class Meta:
        ordering = ['name']
        verbose_name = 'Department'
        verbose_name_plural = 'Departments'

    def __str__(self):
        return self.name

class PositionLevel(models.Model):
    site = models.ForeignKey(
        'tenants.Site',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='position_levels'
    )
    name = models.CharField(max_length=50)
    class Meta:
        ordering = ['name']
        verbose_name = 'Position Level'
        verbose_name_plural = 'Position Levels'

    def __str__(self):
        return self.name
        
class Person(models.Model):
    """Core staff/personnel record"""
    site = models.ForeignKey(
        'tenants.Site',
        on_delete=models.CASCADE,
        related_name='staff',
        null=True,
        blank=True,
        help_text="Site this staff member belongs to"
    )
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('suspended', 'Suspended'),
        ('left', 'Left Company'),
    ]
    
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50, blank=True, null=True)
    employee_id = models.CharField(max_length=25)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True)
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name='staff',
        blank=True,
        null=True,
    )
    position = models.CharField(max_length=30)
    position_level = models.ForeignKey(         
        PositionLevel,                        
        on_delete=models.PROTECT,
        related_name='staff',
        blank=True,
        null=True,
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='person_profile',
        verbose_name='Login Account',
    )

    hire_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    is_archived = models.BooleanField(default=False, db_index=True)
    
    class Meta:
        verbose_name = 'Staff'          
        verbose_name_plural = 'Staff'   
        ordering = ['first_name', 'last_name']
        unique_together = [['site', 'employee_id']]  # Employee ID unique per site
    
    def __str__(self):
        name = self.first_name
        if self.last_name:
            name = f"{self.first_name} {self.last_name}"
        return f"{name} ({self.employee_id})"

class Training(models.Model):
    """Training record"""
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name='trainings')
    training_date = models.DateField(default=timezone.now)
    next_review_date = models.DateField(
        help_text="When training needs to be reviewed/updated",
        blank=True,
        null=True
    )
    policy_category = models.ForeignKey(
        PolicyCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='training_policy_categories',   
        verbose_name="Policy Category",
    )
    linked_policy = ChainedForeignKey(
        PolicyComplianceDocument,
        chained_field="policy_category",
        chained_model_field="category",
        show_all=False,
        auto_choose=True,
        sort=True,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='training_policy_links',        
        verbose_name="Policy Document",
    )

    sop_category = models.ForeignKey(
        SopsCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='training_sop_categories',     
        verbose_name="SOP Category",
    )
    linked_sop = ChainedForeignKey(
        SopsComplianceDocument,
        chained_field="sop_category",
        chained_model_field="category",
        show_all=False,
        auto_choose=True,
        sort=True,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='training_sop_links',          
        verbose_name="SOP Document",
    )

    training_provided = models.CharField(max_length=200)
    trainer = models.CharField(max_length=100, blank=True)
    document = models.FileField(upload_to='training_docs/', blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = ""
        verbose_name_plural = "Training Records"

    def __str__(self):
        return self.training_provided or ""

class Induction(models.Model):
    """Induction checklist"""
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name='inductions')
    induction_date = models.DateField(default=timezone.now)
    next_review_date = models.DateField(
        help_text="When induction needs to be reviewed/updated",
        blank=True,
        null=True
    )

    induction_provided = models.CharField(max_length=200)
    facilitator = models.CharField(max_length=100, blank=True)  
    policy_category = models.ForeignKey(
        PolicyCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='induction_policy_categories',  
        verbose_name="Policy Category",
    )
    linked_policy = ChainedForeignKey(
        PolicyComplianceDocument,
        chained_field="policy_category",
        chained_model_field="category",
        show_all=False,
        auto_choose=True,
        sort=True,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='induction_policy_links',       
        verbose_name="Policy Document",
    )

    sop_category = models.ForeignKey(
        SopsCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='induction_sop_categories',     
        verbose_name="SOP Category",
    )
    linked_sop = ChainedForeignKey(
        SopsComplianceDocument,
        chained_field="sop_category",
        chained_model_field="category",
        show_all=False,
        auto_choose=True,
        sort=True,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='induction_sop_links',          
        verbose_name="SOP Document",
    )

    document = models.FileField(upload_to='induction_docs/', blank=True)
    notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = ""
        verbose_name_plural = "Inductions"

    def __str__(self):
        return self.induction_provided or ""

class Leave(models.Model):
    """Leave record"""
    LEAVE_TYPES = [
        ('annual', 'Annual Leave'),
        ('sick', 'Sick Leave'),
        ('compassionate', 'Compassionate Leave'),
        ('unpaid', 'Unpaid Leave'),
        ('special', 'Special Leave'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ]
    
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name='leaves')
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPES)
    start_date = models.DateField()
    end_date = models.DateField()
    days = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        validators=[MinValueValidator(0.5)],
    )
    reason = models.CharField(max_length=80, blank=True)
    approved_by = models.CharField(max_length=50, blank=True)
    approval_date = models.DateField(blank=True, null=True)
    document = models.FileField(upload_to='leave_docs/', blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-start_date']
        verbose_name_plural = "Leave Records"
    
    def __str__(self):
        return f"{self.person} - {self.get_leave_type_display()} ({self.start_date})"
