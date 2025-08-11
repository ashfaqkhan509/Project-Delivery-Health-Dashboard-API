from django.contrib import admin
from .models import Client, Team, Project, Task, UserBillingInfo


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'manager')
    search_fields = ('name', 'manager__username')


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name', 'members__username')
    filter_horizontal = ('members',)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'client', 'status', 'start_date', 'end_date', 'actual_end_date')
    search_fields = ('name', 'client__name')
    list_filter = ('status', 'start_date', 'end_date')
    raw_id_fields = ('team',)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('name', 'project', 'assigned_user', 'status', 'due_date')
    search_fields = ('name', 'project__name', 'assigned_user__username')
    list_filter = ('status', 'due_date')
    raw_id_fields = ('project', 'assigned_user')


@admin.register(UserBillingInfo)
class UserBillingInfoAdmin(admin.ModelAdmin):
    list_display = ('user', 'task', 'hours_worked', 'hourly_rate', 'is_billible')
    search_fields = ('user__username', 'task__name')
    list_filter = ('is_billible',)
    raw_id_fields = ('user', 'task')


admin.site.site_header = "Project Delivery Health Admin"
