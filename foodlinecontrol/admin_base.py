from django.contrib import admin
from django.contrib.auth import authenticate
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import render, redirect
from django.urls import path, reverse
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.utils.html import format_html


def get_user_site(user):
    """
    Get the site for a user in site admin context.
    - HQ users: Return None (can see all sites' data in HQ context)
    - Site users: Return their assigned_site
    - Site admins: Return the current site from session
    """
    if not user.is_authenticated:
        return None
    
    # Check if this is an HQ user
    try:
        hq_user_site = user.site_profiles.filter(is_hq_user=True, is_archived=False).first()
        if hq_user_site:
            return None  # HQ users see all data
    except Exception:
        pass
    
    # Check if user has a site assignment in session (site admin context)
    # This is set by SiteMiddleware when accessing /hq/{site}/admin/
    if hasattr(user, '_current_site_id'):
        from tenants.models import Site
        try:
            return Site.objects.get(id=user._current_site_id)
        except Exception:
            pass
    
    # Check if user has a site assigned via UserSite
    try:
        site_user = user.site_profiles.filter(is_archived=False, assigned_site__isnull=False).first()
        if site_user:
            return site_user.assigned_site
    except Exception:
        pass
    
    return None

class ArchivedToggleFilter(admin.SimpleListFilter):
    title = "Archived"
    parameter_name = "is_archived"

    def lookups(self, request, model_admin):
        return (
            ("0", "Active"),
            ("1", "Archived"),
            ("all", "All"),
        )

    def queryset(self, request, queryset):
        return queryset


class ArchivableAdmin(admin.ModelAdmin):
    """
    Base admin class for archivable models with protected deletion of archived items.
    
    Deletion Protection:
    - Active items: Can be deleted normally (they should be archived first)
    - Archived items (superuser): Must re-enter password to confirm deletion
    - Archived items (non-superuser): Creates a deletion request for superuser approval
    """
    class Media:
        js = ('js/admin_actions_guard.js',)
        
    change_list_template = "admin/archivable_change_list.html"
    actions = ["archive_selected", "restore_selected"]
    list_filter = (ArchivedToggleFilter,)

    # --- actions (unchanged) ---
    def archive_selected(self, request, queryset):
        updated = queryset.update(is_archived=True)
        self.message_user(request, f"{updated} item(s) archived.")
    archive_selected.short_description = "Archive selected items"

    def restore_selected(self, request, queryset):
        updated = queryset.update(is_archived=False)
        self.message_user(request, f"{updated} item(s) restored.")
    restore_selected.short_description = "Restore selected items"

    # --- actions visibility (unchanged) ---
    def get_actions(self, request):
        actions = super().get_actions(request)
        flag = request.GET.get("is_archived")
        if flag in (None, "", "0"):
            actions.pop("restore_selected", None)
        if flag == "1":
            actions.pop("archive_selected", None)
        return actions

    # --- list view queryset (for changelist only) ---
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        flag = request.GET.get("is_archived")
        if request.resolver_match.url_name.endswith("_changelist"):
            if flag == "1":
                return qs.filter(is_archived=True)
            if flag == "0":
                return qs.filter(is_archived=False)
            if flag == "all":
                return qs
            return qs.filter(is_archived=False)
        # For other views (change form, delete confirm etc.), see all
        return qs

    # --- Protected deletion for archived items ---
    
    def get_urls(self):
        """Add custom URL for protected delete confirmation"""
        urls = super().get_urls()
        info = self.model._meta.app_label, self.model._meta.model_name
        custom_urls = [
            path(
                '<path:object_id>/protected-delete/',
                self.admin_site.admin_view(self.protected_delete_view),
                name='%s_%s_protected_delete' % info,
            ),
        ]
        return custom_urls + urls
    
    def delete_view(self, request, object_id, extra_context=None):
        """Override delete view to add protection for archived items"""
        obj = self.get_object(request, object_id)
        
        if obj and hasattr(obj, 'is_archived') and obj.is_archived:
            # Redirect to protected delete view for archived items
            info = self.model._meta.app_label, self.model._meta.model_name
            return redirect(
                reverse('admin:%s_%s_protected_delete' % info, args=[object_id])
            )
        
        # Normal delete for non-archived items
        return super().delete_view(request, object_id, extra_context)
    
    def protected_delete_view(self, request, object_id):
        """
        Custom view for deleting archived items with extra protection.
        - Superusers: Must re-enter password
        - Non-superusers: Create a deletion request
        """
        from .models import DeletionRequest
        
        obj = self.get_object(request, object_id)
        if not obj:
            messages.error(request, "Object not found.")
            return redirect(self._get_changelist_url())
        
        # Check if item is actually archived
        if not getattr(obj, 'is_archived', False):
            messages.warning(request, "This item is not archived. Use normal delete.")
            info = self.model._meta.app_label, self.model._meta.model_name
            return redirect(reverse('admin:%s_%s_delete' % info, args=[object_id]))
        
        opts = self.model._meta
        object_repr = str(obj)
        
        if request.user.is_superuser:
            # Superuser flow: require password confirmation
            if request.method == 'POST':
                password = request.POST.get('password', '')
                confirm = request.POST.get('confirm_delete', '')
                
                if confirm == 'yes' and password:
                    # Verify password
                    user = authenticate(
                        request, 
                        username=request.user.username, 
                        password=password
                    )
                    if user is not None and user == request.user:
                        # Password correct - proceed with deletion
                        obj.delete()
                        messages.success(
                            request, 
                            f"Successfully deleted archived item: {object_repr}"
                        )
                        return redirect(self._get_changelist_url())
                    else:
                        messages.error(request, "Incorrect password. Deletion cancelled.")
                elif confirm == 'no':
                    messages.info(request, "Deletion cancelled.")
                    return redirect(self._get_changelist_url())
                else:
                    messages.error(request, "Please enter your password to confirm deletion.")
            
            # Show password confirmation form for superuser
            context = {
                **self.admin_site.each_context(request),
                'title': f'Delete archived item: {object_repr}',
                'object': obj,
                'object_name': str(opts.verbose_name),
                'opts': opts,
                'is_superuser': True,
                'app_label': opts.app_label,
                'preserved_filters': self.get_preserved_filters(request),
            }
            return render(request, 'admin/protected_delete_confirmation.html', context)
        
        else:
            # Non-superuser flow: create deletion request
            if request.method == 'POST':
                reason = request.POST.get('reason', '')
                submit_request = request.POST.get('submit_request', '')
                
                if submit_request == 'yes':
                    # Check if a pending request already exists
                    content_type = ContentType.objects.get_for_model(obj)
                    existing = DeletionRequest.objects.filter(
                        content_type=content_type,
                        object_id=obj.pk,
                        status='pending'
                    ).exists()
                    
                    if existing:
                        messages.warning(
                            request, 
                            f"A deletion request for '{object_repr}' is already pending."
                        )
                    else:
                        # Create the deletion request
                        DeletionRequest.objects.create(
                            requested_by=request.user,
                            content_type=content_type,
                            object_id=obj.pk,
                            object_repr=object_repr[:500],  # Limit length
                            reason=reason,
                        )
                        messages.success(
                            request, 
                            f"Deletion request for '{object_repr}' has been submitted. "
                            "A superuser will review your request."
                        )
                    return redirect(self._get_changelist_url())
                elif submit_request == 'no':
                    messages.info(request, "Deletion request cancelled.")
                    return redirect(self._get_changelist_url())
            
            # Show request form for non-superuser
            context = {
                **self.admin_site.each_context(request),
                'title': f'Request deletion of archived item: {object_repr}',
                'object': obj,
                'object_name': str(opts.verbose_name),
                'opts': opts,
                'is_superuser': False,
                'app_label': opts.app_label,
                'preserved_filters': self.get_preserved_filters(request),
            }
            return render(request, 'admin/protected_delete_confirmation.html', context)
    
    def _get_changelist_url(self):
        """Helper to get the changelist URL for this model"""
        info = self.model._meta.app_label, self.model._meta.model_name
        return reverse('admin:%s_%s_changelist' % info)
    
    def has_delete_permission(self, request, obj=None):
        """
        Override to prevent direct deletion of archived items via bulk actions.
        The actual deletion protection is in delete_view and protected_delete_view.
        """
        return super().has_delete_permission(request, obj)


class SiteAwareAdmin(admin.ModelAdmin):
    """
    Admin class that filters querysets by the current site.
    Use this for any model that has a 'site' ForeignKey.
    """
    
    def get_queryset(self, request):
        """Filter queryset by current site from session"""
        qs = super().get_queryset(request)
        
        # Check if model has site field
        if not hasattr(self.model, 'site'):
            return qs
        
        # Get site from session (set by middleware)
        site_id = request.session.get('current_site_id')
        
        if site_id:
            return qs.filter(site_id=site_id)
        
        # If no site in session, show all (HQ mode)
        return qs
    
    def save_model(self, request, obj, form, change):
        """Auto-assign site when creating new objects"""
        if not change and hasattr(obj, 'site') and not obj.site_id:
            site_id = request.session.get('current_site_id')
            if site_id:
                obj.site_id = site_id
        super().save_model(request, obj, form, change)
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter FK dropdowns by current site where applicable"""
        if db_field.name == 'site':
            # Don't filter the site dropdown itself
            pass
        elif hasattr(db_field.related_model, 'site'):
            # Filter related models by current site
            site_id = request.session.get('current_site_id')
            if site_id:
                kwargs['queryset'] = db_field.related_model.objects.filter(site_id=site_id)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class SiteAwareArchivableAdmin(SiteAwareAdmin, ArchivableAdmin):
    """Combined admin with both site filtering and archivable features"""
    pass

