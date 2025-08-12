from django.contrib import admin
from .models import Client, Team, Project, Task, UserBillingInfo, CustomUser
from django.contrib.auth.admin import UserAdmin


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    """
    Admin interface customization for the CustomUser model.
    Displays and manages user credentials, personal information, and permissions.
    """
    model = CustomUser
    list_display = ('email', 'is_staff', 'is_active', 'is_manager')
    list_filter = ('is_staff', 'is_active', 'is_superuser')
    search_fields = ('email',)
    ordering = ('email',)

    fieldsets = (
        ('Login Credentials', {
            'fields': ('email', 'password')
        }),
        ('Personal Info', {
            'fields': ('first_name', 'last_name', 'is_manager')
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        })
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'is_staff', 'is_active', 'is_manager')
        }),
    )


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    """
    Admin interface for managing clients.
    Allows searching and listing client names.
    """
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    """
    Admin interface for managing teams.
    Supports member search and horizontal member selection.
    """
    list_display = ("name",)
    search_fields = ("name", "members__first_name", "memebers__last_name")
    filter_horizontal = ("members",)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    """
    Admin interface for managing projects.
    Displays project details and allows filtering by status and dates.
    """
    list_display = ("name", "client", "status", "start_date", "end_date", "actual_end_date")
    search_fields = ("name", "client__name")
    list_filter = ("status", "start_date", "end_date")
    raw_id_fields = ("team",)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    """
    Admin interface for managing tasks.
    Shows assigned user, project, status, and due date.
    """
    list_display = ("name", "project", "assigned_user", "status", "due_date", "total_hours_worked")
    search_fields = ("name", "project__name", "assigned_user__username")
    list_filter = ("status", "due_date")
    raw_id_fields = ("project", "assigned_user")


@admin.register(UserBillingInfo)
class UserBillingInfoAdmin(admin.ModelAdmin):
    """
    Admin interface for managing user billing information.
    Displays hourly rates and supports user search.
    """
    list_display = ("user", "hourly_rate")
    search_fields = ("user__username",)


admin.site.site_header = "Project Delivery Health Admin"
