"""
Signals for user creation and linking to sites
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from tenants.models import UserSite, Site
from threading import local

# Store current site context
_thread_locals = local()

def get_current_site_id():
    """Get the current site ID from thread local storage"""
    return getattr(_thread_locals, 'current_site_id', None)

def set_current_site_id(site_id):
    """Set the current site ID in thread local storage"""
    _thread_locals.current_site_id = site_id

def clear_current_site_id():
    """Clear the current site ID from thread local storage"""
    if hasattr(_thread_locals, 'current_site_id'):
        del _thread_locals.current_site_id

@receiver(post_save, sender=User)
def auto_link_user_to_site(sender, instance, created, **kwargs):
    """
    When a new User is created, automatically link it to the current site
    if we're in a site-specific admin context.
    """
    if created:
        # Get the current site ID from thread local storage
        # (This will be set by middleware or admin when processing site-specific requests)
        current_site_id = get_current_site_id()
        
        # Only proceed if we have a site context and no UserSite already exists
        if current_site_id:
            try:
                site = Site.objects.get(id=current_site_id)
                
                # Check if UserSite already exists
                user_site_exists = UserSite.objects.filter(
                    user=instance,
                    assigned_site=site
                ).exists()
                
                if not user_site_exists:
                    # Create the UserSite record
                    UserSite.objects.create(
                        user=instance,
                        assigned_site=site,
                        is_hq_user=False,
                        is_archived=False,
                    )
            except Site.DoesNotExist:
                pass
