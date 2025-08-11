from health_delivery_app.models import *
from rest_framework import serializers
from django.utils import timezone
from django.db.models import Sum, F, Count, Q, ExpressionWrapper, FloatField, Window
from django.db.models.functions import DenseRank, TruncDate
from datetime import timedelta


class ProjectSerializer(serializers.ModelSerializer):
    task_completion_percentage = serializers.SerializerMethodField()
    average_task_delay = serializers.SerializerMethodField()
    amount_spent = serializers.SerializerMethodField()
    team_delivery_speed = serializers.SerializerMethodField()
    lead_developer = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            'id', 'name', 'description', 'client', 'budget', 'status',
            'start_date', 'end_date', 'actual_end_date',
            'task_completion_percentage', 'average_task_delay',
            'amount_spent', 'team_delivery_speed', 'lead_developer'
        ]

    def get_task_completion_percentage(self, obj):
        total_tasks = obj.tasks.count()
        completed_tasks = obj.tasks.filter(status=ProjectStatusChoice.COMPLETED).count()
        return (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0

    def get_average_task_delay(self, obj):
        delayed_tasks = obj.tasks.filter(status=ProjectStatusChoice.OVERDUE)
        if not delayed_tasks:
            return 0
        total_delay = sum((task.due_date - task.project.start_date).days for task in delayed_tasks)
        return total_delay / delayed_tasks.count()

    def get_amount_spent(self, obj):
        client = obj.client  # This is the Client instance from the Project
        result = UserBillingInfo.objects.filter(
            task__project__client=client
        ).aggregate(
            total=Sum(
                F('hours_worked') * F('hourly_rate'),
                filter=Q(is_billible=True)
            )
        )
        return result['total']

    def get_team_delivery_speed(self, obj):
        last_30_days = timezone.now() - timedelta(days=30)
        tasks_completed = obj.tasks.filter(
            status=ProjectStatusChoice.COMPLETED,
            actual_end_date__gte=last_30_days
        ).count()
        return f"{round(tasks_completed / 30, 2)} task/day" if tasks_completed > 0 else 0

    def get_lead_developer(self, obj):
        lead_developer = obj.tasks.values(
            "assigned_user__username"
        ).annotate(
            total_tasks=Count('id')
        ).order_by('-total_tasks').first()
        return lead_developer["assigned_user__username"] if lead_developer else None


class ClientSerializer(serializers.ModelSerializer):
    total_projects = serializers.SerializerMethodField()
    total_budget = serializers.SerializerMethodField()
    total_amount_spent = serializers.SerializerMethodField()
    overall_delivery_health = serializers.SerializerMethodField()
    overdue_projects = serializers.SerializerMethodField()
    top_3_teams_by_average_task_delivery_speed_last_30_days = serializers.SerializerMethodField()
    projects = ProjectSerializer(many=True, read_only=True)

    class Meta:
        model = Client
        fields = [
            'id', 'name', 'manager', 'total_projects', 'total_budget',
            'total_amount_spent', 'overall_delivery_health', 'overdue_projects',
            'top_3_teams_by_average_task_delivery_speed_last_30_days', 'projects'
        ]

    def get_total_projects(self, obj):
        return obj.projects.count()

    def get_total_budget(self, obj):
        return obj.projects.aggregate(total=Sum('budget'))['total']

    def get_total_amount_spent(self, obj):
        result = UserBillingInfo.objects.filter(
            task__project__client=obj
        ).aggregate(
            total=Sum(
                F('hours_worked') * F('hourly_rate'),
                filter=Q(is_billible=True)
            )
        )
        return result['total']

    def get_overall_delivery_health(self, obj):

        completed_projects = obj.projects.filter(
            status=ProjectStatusChoice.COMPLETED
        )

        total_completed_projects = completed_projects.count()

        number_of_projects_completed_on_time = completed_projects.filter(
            actual_end_date__lte=F('end_date')
        ).count()

        percentage_completed_on_time = (
            (number_of_projects_completed_on_time / total_completed_projects * 100)
            if total_completed_projects > 0 else 0
        )

        if percentage_completed_on_time >= 80:
            return "on_track"
        elif percentage_completed_on_time >= 50:
            return "at_risk"
        else:
            return "delayed"

    def get_overdue_projects(self, obj):
        return obj.projects.filter(
            status=ProjectStatusChoice.OVERDUE
        ).count()

    def get_top_3_teams_by_average_task_delivery_speed_last_30_days(self, obj):
        last_30_days = timezone.now() - timedelta(days=30)

        recent_tasks = (
            Task.objects.filter(
                project__client=obj,
                status=ProjectStatusChoice.COMPLETED,
                actual_end_date__gte=last_30_days
            )
            .values(
                'project__team__id',
                'project__team__name'
            )
            .annotate(
                total_tasks_completed=Count('id'),
                avg_tasks_per_day=ExpressionWrapper(
                    Count('id') / 30.0,
                    output_field=FloatField()
                )
            )
            .annotate(
                rank=Window(
                    expression=DenseRank(),
                    order_by=F("avg_tasks_per_day").desc()
                )
            )
            .filter(rank__lte=3)
            .order_by('rank', '-avg_tasks_per_day')
        )

        return [team['project__team__name'] for team in recent_tasks]
