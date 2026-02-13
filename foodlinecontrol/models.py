"""
Core models for FoodLineControl - includes DeletionRequest for protected archive deletion
"""
from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone


class DeletionRequest(models.Model):
    """
    Stores requests from non-superusers to delete archived records.
    Superusers can approve or reject these requests.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    # Who requested the deletion
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='deletion_requests_made',
        verbose_name="Requested By"
    )
    
    # When was it requested
    requested_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Requested At"
    )
    
    # Generic foreign key to any model
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        verbose_name="Content Type"
    )
    object_id = models.PositiveIntegerField(verbose_name="Object ID")
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Store the object representation for display after deletion
    object_repr = models.CharField(
        max_length=500,
        verbose_name="Object Description",
        help_text="String representation of the object at time of request"
    )
    
    # Reason for deletion request
    reason = models.TextField(
        blank=True,
        verbose_name="Reason for Deletion",
        help_text="Why should this archived item be permanently deleted?"
    )
    
    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="Status"
    )
    
    # Who handled the request (superuser)
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deletion_requests_handled',
        verbose_name="Handled By"
    )
    
    # When was it handled
    handled_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Handled At"
    )
    
    # Response from superuser
    admin_notes = models.TextField(
        blank=True,
        verbose_name="Admin Notes",
        help_text="Notes from the administrator about this request"
    )
    
    class Meta:
        verbose_name = "Deletion Request"
        verbose_name_plural = "Deletion Requests"
        ordering = ['-requested_at']
    
    def __str__(self):
        return f"Delete {self.object_repr} - {self.get_status_display()}"
    
    def approve(self, user, notes=''):
        """Approve and execute the deletion"""
        self.status = 'approved'
        self.handled_by = user
        self.handled_at = timezone.now()
        self.admin_notes = notes
        self.save()
        
        # Actually delete the object if it still exists
        if self.content_object:
            self.content_object.delete()
    
    def reject(self, user, notes=''):
        """Reject the deletion request"""
        self.status = 'rejected'
        self.handled_by = user
        self.handled_at = timezone.now()
        self.admin_notes = notes
        self.save()
