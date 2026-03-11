"""
Multi-site models - Simple FK-based approach (no django-tenants)
"""
from django.db import models
from django.core.validators import FileExtensionValidator
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password, check_password
import threading

# Thread local storage for current site
_thread_locals = threading.local()


def get_current_site():
    """Get the current site from thread local storage"""
    return getattr(_thread_locals, 'site', None)


def set_current_site(site):
    """Set the current site in thread local storage"""
    _thread_locals.site = site


class SiteManager(models.Manager):
    """Manager that filters by current site"""
    
    def get_queryset(self):
        qs = super().get_queryset()
        site = get_current_site()
        # Only filter if we have a site context
        if site:
            return qs.filter(site=site)
        return qs
    
    def for_site(self, site):
        """Explicitly filter for a specific site"""
        return super().get_queryset().filter(site=site)
    
    def all_sites(self):
        """Return queryset for all sites (bypass filtering)"""
        return super().get_queryset()
    
    def hq_only(self):
        """Return queryset for HQ-only data (site=NULL)"""
        return super().get_queryset().filter(site__isnull=True)


class SiteAwareModel(models.Model):
    """
    Abstract base model for site-aware data.
    - site=None means HQ-only data
    - site=X means data belongs to site X
    """
    site = models.ForeignKey(
        'tenants.Site',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='%(class)s_items',
        help_text="Site this record belongs to. Leave blank for HQ-only data."
    )
    
    # Use standard manager by default for admin/shell
    objects = models.Manager()
    # Site-filtered manager
    site_objects = SiteManager()
    
    class Meta:
        abstract = True


class Site(models.Model):
    """
    Represents a manufacturing site/factory.
    Data isolation via FK filtering, not schemas.
    """
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True, help_text="URL-friendly name (auto-generated from name)")
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_archived = models.BooleanField(default=False, db_index=True)
    
    # Admin Appearance
    admin_background = models.ImageField(
        upload_to="sites/backgrounds/",
        blank=True,
        null=True,
        verbose_name="Admin Background Image",
        help_text="Background image displayed on the admin dashboard for this site (JPEG/PNG).",
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'gif', 'webp'])],
    )
    
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Site"
        verbose_name_plural = "Sites"
        ordering = ['name']

    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        """Auto-generate slug from name if not provided"""
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def get_admin_url(self):
        """Return the admin URL for this site"""
        return f"/hq/{self.slug}/admin/"


class UserSite(models.Model):
    """
    Links users to sites they can access.
    - HQ users: is_hq_user=True, can access all sites + /hq/ dashboard
      - Authenticated with hq_username + hq_password (encrypted)
      - user field is optional (not needed for HQ)
    - Site users: assigned to specific site only
      - Authenticated with Django User credentials
      - Cannot access /hq/ at all
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='site_profiles',
        null=True,
        blank=True,
        help_text="Django user (required for site users, optional for HQ users)"
    )
    assigned_site = models.ForeignKey(
        Site, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='assigned_users',
        help_text="Site this user belongs to (leave blank for HQ users)"
    )
    is_hq_user = models.BooleanField(
        default=False, 
        help_text="HQ users can access /hq/ dashboard and ALL sites. Site users cannot access HQ."
    )
    
    # HQ Credentials - Only populated when is_hq_user=True
    hq_username = models.CharField(
        max_length=150,
        unique=True,
        null=True,
        blank=True,
        help_text="Unique HQ login username. Only for HQ users."
    )
    hq_password = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="HQ login password (encrypted with PBKDF2). Only for HQ users."
    )
    email = models.EmailField(
        max_length=254,
        blank=True,
        default='',
        help_text="User's email address. Used as Reply-To when sending documents."
    )
    is_manager = models.BooleanField(
        default=False,
        help_text="Site Manager"
    )
    
    is_archived = models.BooleanField(default=False, db_index=True)
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User Site Assignment"
        verbose_name_plural = "User Site Assignments"

    def __str__(self):
        # HQ users use hq_username instead of Django user
        if self.is_hq_user:
            return f"👤 {self.hq_username} (HQ Admin)" if self.hq_username else "(HQ User - No Username)"
        # Site users use Django user
        elif self.user:
            if self.assigned_site:
                return f"👤 {self.user.username} ({self.assigned_site.name})"
            return f"👤 {self.user.username} (No site)"
        # Fallback for orphaned records
        return "(No user - No site)"

    def can_access_site(self, site):
        """Check if user can access a specific site"""
        if self.is_hq_user:
            return True
        return self.assigned_site_id == site.id if self.assigned_site else False

    def can_access_hq(self):
        """Check if user can access HQ dashboard"""
        return self.is_hq_user
    
    def set_hq_password(self, raw_password):
        """Hash and set HQ password using Django's PBKDF2"""
        if raw_password:
            self.hq_password = make_password(raw_password)
        else:
            self.hq_password = None
    
    def check_hq_password(self, raw_password):
        """Check if provided password matches the hashed HQ password"""
        if not self.hq_password or not raw_password:
            return False
        return check_password(raw_password, self.hq_password)
    
    def get_login_redirect_url(self):
        """Where to redirect user after login"""
        if self.is_hq_user:
            return '/hq/'
        elif self.assigned_site:
            return f'/hq/{self.assigned_site.slug}/admin/'
        return '/hq/'  # Fallback
    
    def save(self, *args, **kwargs):
        """Auto-set is_hq_user=True when hq_username is provided"""
        # If hq_username is set, this is an HQ user
        if self.hq_username:
            self.is_hq_user = True
            self.user = None  # HQ users don't need Django user
            self.assigned_site = None  # HQ users can access ALL sites
        super().save(*args, **kwargs)
