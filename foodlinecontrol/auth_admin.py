from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin, GroupAdmin as BaseGroupAdmin
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.http import JsonResponse
from django import forms
from human_resources.models import Department, PositionLevel, Person
from tenants.models import UserSite

User = get_user_model()

try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass

try:
    admin.site.unregister(Group)
except admin.sites.NotRegistered:
    pass


# Custom filter for User active/archived status (using is_active field)
class UserActiveFilter(admin.SimpleListFilter):
    title = "Status"
    parameter_name = "is_active"

    def lookups(self, request, model_admin):
        return (
            ("1", "Active"),
            ("0", "Archived"),
            ("all", "All"),
        )

    def queryset(self, request, queryset):
        return queryset


# Custom filter for Group archived status (using is_archived field)
class GroupArchivedFilter(admin.SimpleListFilter):
    title = "Status"
    parameter_name = "is_archived"

    def lookups(self, request, model_admin):
        return (
            ("0", "Active"),
            ("1", "Archived"),
            ("all", "All"),
        )

    def queryset(self, request, queryset):
        return queryset


class StaffSelectForm(forms.Form):
    department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        required=False,
        label="Department",
    )
    position_level = forms.ModelChoiceField(
        queryset=PositionLevel.objects.none(),
        required=False,
        label="Position level",
    )
    person = forms.ModelChoiceField(
        queryset=Person.objects.none(),
        required=False,
        label="Employee",
    )

    def __init__(self, *args, **kwargs):
        # Extract site_id if passed
        site_id = kwargs.pop('site_id', None)
        super().__init__(*args, **kwargs)
        data = self.data or self.initial

        dept_id = data.get("department") or None
        
        # Filter by site if site_id provided
        if site_id:
            self.fields["department"].queryset = Department.objects.filter(site_id=site_id)
            self.fields["position_level"].queryset = PositionLevel.objects.filter(site_id=site_id)
        else:
            self.fields["position_level"].queryset = PositionLevel.objects.all()
        
        qs = Person.objects.filter(site_id=site_id) if site_id else Person.objects.all()
        if dept_id:
            qs = qs.filter(department_id=dept_id)

        pos_id = data.get("position_level") or None
        if pos_id:
            qs = qs.filter(position_level_id=pos_id)

        self.fields["person"].queryset = qs


class CustomUserCreationForm(forms.ModelForm):
    """Form to create users with password fields"""
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput,
    )
    password2 = forms.CharField(
        label="Password confirmation",
        widget=forms.PasswordInput,
    )

    class Meta:
        model = User
        fields = ("username", "email")

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2:
            if password1 != password2:
                raise forms.ValidationError("Passwords don't match")
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        user.first_name = ""
        user.last_name = ""
        if commit:
            user.save()
        return user


# =============================================================================
# Custom User Form with Manager Status
# =============================================================================

class CustomUserForm(forms.ModelForm):
    """Extended User form that includes manager status from UserSite"""
    is_manager = forms.BooleanField(
        required=False,
        label="Manager",
        help_text="Site Manager"
    )
    
    class Meta:
        model = User
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pre-populate is_manager from UserSite if user exists
        if self.instance and self.instance.pk:
            try:
                usersite = UserSite.objects.get(user=self.instance, is_hq_user=False)
                self.fields['is_manager'].initial = usersite.is_manager
            except UserSite.DoesNotExist:
                self.fields['is_manager'].initial = False
    
    def save(self, commit=True):
        user = super().save(commit=False)
        
        # Hash password if it was changed and is not already hashed
        if 'password' in self.changed_data:
            password = self.cleaned_data.get('password')
            if password and not password.startswith('pbkdf2_'):
                # Password was changed and is not hashed - hash it
                user.set_password(password)
        
        if commit:
            user.save()
        
        # Update UserSite.is_manager if user exists
        if user.pk and 'is_manager' in self.cleaned_data:
            try:
                usersite = UserSite.objects.get(user=user, is_hq_user=False)
                usersite.is_manager = self.cleaned_data['is_manager']
                usersite.save()
            except UserSite.DoesNotExist:
                pass  # No site assignment yet
        
        return user


@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    change_list_template = "admin/archivable_change_list.html"
    form = CustomUserForm
    actions = ["archive_users", "restore_users"]
    list_filter = (UserActiveFilter, 'is_staff', 'is_superuser', 'groups')
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_manager', 'groups', 'user_permissions'),
        }),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2'),
        }),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'groups', 'user_permissions'),
        }),
    )

    # Archive/Restore actions
    def archive_users(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} user(s) archived (deactivated).")
    archive_users.short_description = "Archive selected users"

    def restore_users(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} user(s) restored (activated).")
    restore_users.short_description = "Restore selected users"

    def get_actions(self, request):
        """Conditionally show archive/restore actions based on filter"""
        actions = super().get_actions(request)
        flag = request.GET.get("is_active")
        
        # If showing only active users, hide restore action
        if flag in (None, "", "1"):
            actions.pop("restore_users", None)
        # If showing only archived users, hide archive action
        if flag == "0":
            actions.pop("archive_users", None)
        
        return actions

    def get_queryset(self, request):
        """
        Filter users based on:
        1. Site context (site-specific users in site admin, all users in HQ)
        2. Active/Archived status filter
        """
        qs = super().get_queryset(request)
        
        # Check if we're in a site context (not HQ)
        current_site_id = request.session.get('current_site_id')
        is_hq_context = request.session.get('is_hq_context', False)
        
        if current_site_id and not is_hq_context:
            # Site context: Show ONLY users assigned to this site
            from tenants.models import UserSite
            
            # Get user IDs assigned to the current site (not HQ users)
            site_user_ids = UserSite.objects.filter(
                assigned_site_id=current_site_id,
                is_hq_user=False,
                is_archived=False
            ).exclude(user__isnull=True).values_list('user_id', flat=True)
            
            # Show only this site's users
            qs = qs.filter(id__in=site_user_ids)
        
        # Filter by active/archived status
        if request.resolver_match.url_name.endswith("_changelist"):
            flag = request.GET.get("is_active")
            if flag == "0":
                # Show archived (inactive) users
                qs = qs.filter(is_active=False)
            elif flag == "1":
                # Show active users
                qs = qs.filter(is_active=True)
            elif flag == "all":
                # Show all users
                pass
            else:
                # Default: show only active users
                qs = qs.filter(is_active=True)
        
        return qs

    def save_model(self, request, obj, form, change):
        """
        Save user and automatically link to site when creating in site context.
        Also ensures password is properly hashed.
        """
        # Check if password needs to be hashed
        if change:  # Editing existing user
            # Get the password from the form data
            password = form.cleaned_data.get('password')
            if password and not password.startswith('pbkdf2_') and not password.startswith('bcrypt') and not password.startswith('argon2'):
                # Password was changed and is not hashed - hash it now
                obj.set_password(password)
        
        # If creating a new user in site context, set thread local for signal
        if not change:  # change=False means it's a new object
            current_site_id = request.session.get('current_site_id')
            is_hq_context = request.session.get('is_hq_context', False)
            
            if current_site_id and not is_hq_context:
                # Set thread local so signal can access it
                from foodlinecontrol.auth_signals import set_current_site_id
                set_current_site_id(current_site_id)
        
        try:
            super().save_model(request, obj, form, change)
        finally:
            # Always clear thread local after saving
            from foodlinecontrol.auth_signals import clear_current_site_id
            clear_current_site_id()

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "add-staff/",
                self.admin_site.admin_view(self.add_staff_view),
                name="auth_user_add_staff",
            ),
            path(
                "get-person-details/",
                self.admin_site.admin_view(self.get_person_details),
                name="get_person_details",
            ),
            path(
                "get-position-levels/",
                self.admin_site.admin_view(self.get_position_levels),
                name="get_position_levels",
            ),
            path(
                "get-persons/",
                self.admin_site.admin_view(self.get_persons),
                name="get_persons",
            ),
        ]
        return custom_urls + urls

    def get_person_details(self, request):
        """API endpoint to get person details (name, email)"""
        person_id = request.GET.get('person_id')
        
        try:
            person = Person.objects.get(pk=person_id)
            # Handle optional last_name
            if person.last_name:
                username = f"{person.first_name.lower()}.{person.last_name.lower()}".replace(" ", "")
            else:
                username = person.first_name.lower().replace(" ", "")
            
            data = {
                'username': username,
                'email': person.email or '',
                'first_name': person.first_name,
                'last_name': person.last_name or '',
            }
            return JsonResponse(data)
        except Person.DoesNotExist:
            return JsonResponse({'error': 'Person not found'}, status=404)

    def get_position_levels(self, request):
        """API endpoint to get all position levels filtered by current site"""
        # Filter by current site
        current_site_id = request.session.get('current_site_id')
        if current_site_id:
            position_levels = PositionLevel.objects.filter(site_id=current_site_id).values('id', 'name')
        else:
            position_levels = PositionLevel.objects.all().values('id', 'name')
        
        data = {
            'position_levels': [
                {'id': p['id'], 'name': p['name']} 
                for p in position_levels
            ]
        }
        return JsonResponse(data)

    def get_persons(self, request):
        """API endpoint to get persons filtered by department, position_level, and site"""
        dept_id = request.GET.get('department_id')
        pos_level_id = request.GET.get('position_level_id')
        
        # Filter by current site first
        current_site_id = request.session.get('current_site_id')
        if current_site_id:
            qs = Person.objects.filter(site_id=current_site_id)
        else:
            qs = Person.objects.all()
        
        if dept_id:
            qs = qs.filter(department_id=dept_id)
        if pos_level_id:
            qs = qs.filter(position_level_id=pos_level_id)
        
        persons = qs.values('id', 'first_name', 'last_name')
        data = {
            'persons': [
                {
                    'id': p['id'], 
                    'name': f"{p['first_name']} {p['last_name']}" if p['last_name'] else p['first_name']
                } 
                for p in persons
            ]
        }
        return JsonResponse(data)

    def add_staff_view(self, request):
        """Combined wizard to select staff person and create user in one form"""
        # Get current site for filtering
        current_site_id = request.session.get('current_site_id')
        
        if request.method == "POST":
            staff_form = StaffSelectForm(request.POST, site_id=current_site_id)
            user_form = CustomUserCreationForm(request.POST)
            
            if staff_form.is_valid() and user_form.is_valid():
                person = staff_form.cleaned_data.get("person")
                if person:
                    # Set site context for signal handler BEFORE creating user
                    current_site_id = request.session.get('current_site_id')
                    is_hq_context = request.session.get('is_hq_context', False)
                    
                    from foodlinecontrol.auth_signals import set_current_site_id, clear_current_site_id
                    
                    if current_site_id and not is_hq_context:
                        set_current_site_id(current_site_id)
                    
                    try:
                        # Save the user - this will trigger post_save signal
                        user = user_form.save(commit=True)  # Explicitly save to DB
                        # Update additional fields
                        user.is_staff = True
                        user.first_name = person.first_name
                        user.last_name = person.last_name or ''  # Django User requires string, not None
                        user.save()  # This second save updates the fields
                        
                        return redirect(reverse("admin:auth_user_change", args=[user.pk]))
                    finally:
                        clear_current_site_id()
        else:
            staff_form = StaffSelectForm(request.GET, site_id=current_site_id)
            user_form = CustomUserCreationForm()

        context = dict(
            self.admin_site.each_context(request),
            opts=self.model._meta,
            title="Add staff user",
            staff_form=staff_form,
            user_form=user_form,
        )
        return render(request, "admin/auth/user/add_staff_wizard.html", context)

    def add_view(self, request, form_url="", extra_context=None):
        """Pre-fill user form when coming from staff wizard"""
        extra_context = extra_context or {}
        person_id = request.GET.get("person")
        
        if person_id:
            try:
                p = Person.objects.get(pk=person_id)
                extra_context["person"] = p
            except Person.DoesNotExist:
                pass
        
        return super().add_view(request, form_url, extra_context=extra_context)

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        person_id = request.GET.get("person")
        if person_id:
            try:
                p = Person.objects.get(pk=person_id)
                # Handle optional last_name
                if p.last_name:
                    base_username = (p.first_name + "." + p.last_name).lower().replace(" ", "")
                else:
                    base_username = p.first_name.lower().replace(" ", "")
                
                initial.update(
                    {
                        "username": base_username,
                        "first_name": p.first_name,
                        "last_name": p.last_name or '',  # Django User requires string, not None
                        "email": p.email or '',  # Django User requires string, not None
                        "is_staff": True,
                    }
                )
            except Person.DoesNotExist:
                pass
        return initial


# =============================================================================
# Site-Level UserSite Admin - For managing site user manager roles (as inline)
# Note: Manager status is now a direct field on User form, not a separate admin
# =============================================================================


# =============================================================================
# DeletionRequest Admin - For managing archived item deletion requests
# =============================================================================

from django.utils.html import format_html
from django.contrib import messages
from django.contrib.auth import authenticate
from .models import DeletionRequest


@admin.register(DeletionRequest)
class DeletionRequestAdmin(admin.ModelAdmin):
    """
    Admin interface for superusers to manage deletion requests.
    Only superusers can access this admin.
    """
    list_display = [
        'object_repr',
        'content_type',
        'requested_by',
        'requested_at',
        'reason_preview',
        'status_badge',
        'handled_by',
        'handled_at',
    ]
    list_filter = ['status', 'content_type', 'requested_at']
    search_fields = ['object_repr', 'reason', 'requested_by__username']
    readonly_fields = [
        'requested_by', 
        'requested_at', 
        'content_type', 
        'object_id',
        'object_repr',
        'reason',
        'handled_by',
        'handled_at',
    ]
    ordering = ['-requested_at']
    actions = ['approve_requests', 'reject_requests']
    
    fieldsets = (
        ('Request Details', {
            'fields': ('object_repr', 'content_type', 'object_id', 'reason'),
        }),
        ('Requester', {
            'fields': ('requested_by', 'requested_at'),
        }),
        ('Status', {
            'fields': ('status', 'handled_by', 'handled_at', 'admin_notes'),
        }),
    )
    
    def has_module_permission(self, request):
        """Only superusers can see this admin"""
        return request.user.is_superuser
    
    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser
    
    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
    
    def has_add_permission(self, request):
        # Deletion requests are created programmatically, not manually
        return False
    
    def reason_preview(self, obj):
        """Show first 50 chars of reason"""
        if obj.reason:
            return obj.reason[:50] + '...' if len(obj.reason) > 50 else obj.reason
        return '-'
    reason_preview.short_description = 'Reason'
    
    def status_badge(self, obj):
        """Display status with colored badge"""
        colors = {
            'pending': '#ffc107',
            'approved': '#28a745',
            'rejected': '#dc3545',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-size: 11px; font-weight: bold;">{}</span>',
            color, obj.get_status_display().upper()
        )
    status_badge.short_description = 'Status'
    
    def approve_requests(self, request, queryset):
        """Bulk approve selected pending requests (requires password)"""
        pending = queryset.filter(status='pending')
        if not pending.exists():
            messages.warning(request, "No pending requests selected.")
            return
        
        # Store IDs in session for the confirmation view
        request.session['pending_approve_ids'] = list(pending.values_list('id', flat=True))
        return redirect(reverse('admin:confirm_bulk_approve'))
    approve_requests.short_description = "Approve selected requests (requires password)"
    
    def reject_requests(self, request, queryset):
        """Bulk reject selected pending requests"""
        updated = queryset.filter(status='pending').count()
        for req in queryset.filter(status='pending'):
            req.reject(request.user, notes="Bulk rejected by admin")
        messages.success(request, f"{updated} request(s) rejected.")
    reject_requests.short_description = "Reject selected requests"
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'confirm-bulk-approve/',
                self.admin_site.admin_view(self.confirm_bulk_approve_view),
                name='confirm_bulk_approve',
            ),
        ]
        return custom_urls + urls
    
    def confirm_bulk_approve_view(self, request):
        """View to confirm bulk approval with password"""
        pending_ids = request.session.get('pending_approve_ids', [])
        if not pending_ids:
            messages.error(request, "No requests to approve.")
            return redirect(reverse('admin:foodlinecontrol_deletionrequest_changelist'))
        
        pending_requests = DeletionRequest.objects.filter(id__in=pending_ids, status='pending')
        
        if request.method == 'POST':
            password = request.POST.get('password', '')
            confirm = request.POST.get('confirm', '')
            
            if confirm == 'yes' and password:
                user = authenticate(
                    request,
                    username=request.user.username,
                    password=password
                )
                if user is not None and user == request.user:
                    # Password correct - approve all
                    count = 0
                    for req in pending_requests:
                        req.approve(request.user, notes="Bulk approved by admin")
                        count += 1
                    
                    # Clear session
                    del request.session['pending_approve_ids']
                    
                    messages.success(request, f"{count} deletion request(s) approved and items deleted.")
                    return redirect(reverse('admin:foodlinecontrol_deletionrequest_changelist'))
                else:
                    messages.error(request, "Incorrect password. Approval cancelled.")
            elif confirm == 'no':
                del request.session['pending_approve_ids']
                messages.info(request, "Approval cancelled.")
                return redirect(reverse('admin:foodlinecontrol_deletionrequest_changelist'))
        
        context = {
            **self.admin_site.each_context(request),
            'title': 'Confirm Bulk Approval',
            'pending_requests': pending_requests,
            'opts': self.model._meta,
        }
        return render(request, 'admin/confirm_bulk_approve.html', context)
    
    def change_view(self, request, object_id, form_url='', extra_context=None):
        """Custom change view to handle approve/reject actions with password"""
        obj = self.get_object(request, object_id)
        extra_context = extra_context or {}
        
        if request.method == 'POST' and obj and obj.status == 'pending':
            action = request.POST.get('action_type', '')
            password = request.POST.get('action_password', '')
            notes = request.POST.get('admin_notes', '')
            
            if action in ('approve', 'reject') and password:
                user = authenticate(
                    request,
                    username=request.user.username,
                    password=password
                )
                if user is not None and user == request.user:
                    if action == 'approve':
                        obj.approve(request.user, notes=notes)
                        messages.success(request, f"Request approved. '{obj.object_repr}' has been deleted.")
                    else:
                        obj.reject(request.user, notes=notes)
                        messages.success(request, f"Request rejected.")
                    return redirect(reverse('admin:foodlinecontrol_deletionrequest_changelist'))
                else:
                    messages.error(request, "Incorrect password. Action cancelled.")
        
        extra_context['show_action_buttons'] = obj and obj.status == 'pending'
        return super().change_view(request, object_id, form_url, extra_context)


# =============================================================================
# GROUP ADMIN WITH ARCHIVE FUNCTIONALITY
# =============================================================================

@admin.register(Group)
class CustomGroupAdmin(BaseGroupAdmin):
    change_list_template = "admin/archivable_change_list.html"
    actions = ["archive_groups", "restore_groups"]
    list_filter = (GroupArchivedFilter, )
    list_display = ('name', 'get_permission_count')
    
    def get_permission_count(self, obj):
        """Show number of permissions in this group"""
        return obj.permissions.count()
    get_permission_count.short_description = 'Permissions'
    
    # Archive/Restore actions
    def archive_groups(self, request, queryset):
        from django.db import connection
        group_ids = list(queryset.values_list('id', flat=True))
        if group_ids:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"UPDATE auth_group SET is_archived = TRUE WHERE id IN ({','.join(['%s'] * len(group_ids))})",
                    group_ids
                )
        self.message_user(request, f"{len(group_ids)} group(s) archived.")
    archive_groups.short_description = "Archive selected groups"

    def restore_groups(self, request, queryset):
        from django.db import connection
        group_ids = list(queryset.values_list('id', flat=True))
        if group_ids:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"UPDATE auth_group SET is_archived = FALSE WHERE id IN ({','.join(['%s'] * len(group_ids))})",
                    group_ids
                )
        self.message_user(request, f"{len(group_ids)} group(s) restored.")
    restore_groups.short_description = "Restore selected groups"

    def get_actions(self, request):
        """Conditionally show archive/restore actions based on filter"""
        actions = super().get_actions(request)
        flag = request.GET.get("is_archived")
        
        # If showing only active groups, hide restore action
        if flag in (None, "", "0"):
            actions.pop("restore_groups", None)
        # If showing only archived groups, hide archive action
        if flag == "1":
            actions.pop("archive_groups", None)
        
        return actions

    def get_queryset(self, request):
        """
        Filter groups based on archived status using raw SQL
        The is_archived field exists in the database but not in Django's Group model
        """
        qs = super().get_queryset(request)
        
        # Filter by archived status using .extra() to access the database field
        if request.resolver_match.url_name.endswith("_changelist"):
            flag = request.GET.get("is_archived")
            if flag == "1":
                # Show archived groups
                qs = qs.extra(where=["auth_group.is_archived = TRUE"])
            elif flag == "0":
                # Show active groups
                qs = qs.extra(where=["auth_group.is_archived = FALSE"])
            elif flag == "all":
                # Show all groups
                pass
            else:
                # Default: show only active groups
                qs = qs.extra(where=["auth_group.is_archived = FALSE"])
        
        return qs

