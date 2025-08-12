from health_delivery_app.models import (
    CustomUser,
    Client,
    Project,
    Task,
    UserBillingInfo,
    ProjectStatusChoice,
    TaskStatusChoice
)
from rest_framework import serializers
from django.utils import timezone
from django.db.models import Sum, F, Count, Q, ExpressionWrapper, FloatField, Window
from django.db.models.functions import DenseRank
from datetime import timedelta


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'email', 'first_name', 'last_name', 'is_manager']


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'password', 'is_manager', 'confirm_password']

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError("Passwords do not match.")
        if CustomUser.objects.filter(email=data['email']).exists():
            raise serializers.ValidationError("Email already exists.")

        return data

    def create(self, validated_data):
        validated_data.pop('confirm_password')
        user = CustomUser.objects.create_user(**validated_data)
        return user


class UserLoginSerializer(serializers.Serializer):
    """
    Serializer for user login.
    Accepts username and password.
    """
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


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
        completed_tasks = obj.tasks.filter(status=TaskStatusChoice.DONE).count()
        return (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0

    def get_average_task_delay(self, obj):
        delayed_tasks = obj.tasks.filter(
            actual_end_date__isnull=False,
            actual_end_date__gt = F('due_date')
        )
        if not delayed_tasks:
            return 0
        total_delay = sum(
            (task.actual_end_date - task.due_date).days 
            for task in delayed_tasks
        )
        return total_delay / delayed_tasks.count()

    def get_amount_spent(self, obj):
        total = obj.tasks.filter(
            assigned_user__billing_info__isnull=False,
            total_hours_worked__gt=0
        ).aggregate(
            total_amount=Sum(F('total_hours_worked') * F('assigned_user__billing_info__hourly_rate'))
        )['total_amount'] or 0
        
        return round(total, 2)

    def get_team_delivery_speed(self, obj):
        """
        Calculate average tasks completed per day in the last 30 days for the team.
        """
        if not obj.team:
            return 0.0
        
        thirty_days_ago = timezone.now().date() - timedelta(days=30)
        
        result = Task.objects.filter(
            project__team=obj.team,
            status=TaskStatusChoice.DONE,
            actual_end_date__range=(thirty_days_ago, timezone.now().date())
        ).aggregate(
            total_tasks=Count('id')
        )
    
        total_tasks = result['total_tasks'] or 0
        
        return round(total_tasks / 30, 2)

    def get_lead_developer(self, obj):
        lead_developer = obj.tasks.values(
            "assigned_user__email"
        ).annotate(
            total_tasks=Count('id')
        ).order_by('-total_tasks').first()
        return lead_developer["assigned_user__email"] if lead_developer else None


class ClientSerializer(serializers.ModelSerializer):
    total_projects = serializers.SerializerMethodField()
    total_budget = serializers.SerializerMethodField()
    overall_delivery_health = serializers.SerializerMethodField()
    overdue_projects = serializers.SerializerMethodField()
    top_3_teams_by_average_task_delivery_speed_last_30_days = serializers.SerializerMethodField()
    projects = ProjectSerializer(many=True, read_only=True)

    class Meta:
        model = Client
        fields = [
            'id', 'name', 'total_projects', 'total_budget',
            'overall_delivery_health', 'overdue_projects',
            'top_3_teams_by_average_task_delivery_speed_last_30_days', 'projects'
        ]

    def get_total_projects(self, obj):
        return obj.projects.count()

    def get_total_budget(self, obj):
        return obj.projects.aggregate(total=Sum('budget'))['total']

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
                status=TaskStatusChoice.DONE,
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
