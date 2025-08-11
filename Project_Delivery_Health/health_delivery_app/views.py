
from rest_framework import viewsets
from health_delivery_app.models import Client, Project, ProjectStatusChoice
from health_delivery_app.serializers import ClientSerializer
from django.utils import timezone
from datetime import timedelta, datetime
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, F, Count, Q, ExpressionWrapper, FloatField, Case, When, Value
from rest_framework.filters import OrderingFilter
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.http import HttpResponse
import csv
import io


class ProjectHealthViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that provides project health metrics for clients.

    This viewset returns a list of clients with detailed project health information,
    including financial metrics, delivery performance, and team productivity.

    Features:
    - Authentication required (IsAuthenticated)
    - Filtering by project status, budget, and start date
    - Ordering by financial and performance metrics
    - Automatic pagination
    - Permission-based data access (managers only see their clients)

    Default Behavior:
    - Returns clients with active projects from the last 90 days
    - Includes nested project information with health metrics
    """
    queryset = Project.objects.all()
    serializer_class = ClientSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [OrderingFilter]
    ordering_fields = ["amount_spent", "overall_delivery_health", ""]

    def get_queryset(self):
        """
        Returns a filtered queryset of clients based on request parameters.

        Handles:
        - User permissions (non-superusers only see their managed clients)
        - Status filtering (?status=active|completed|overdue)
        - Budget filtering (?min_budget=10000)
        - Date range filtering (?start_after=YYYY-MM-DD)
        - Custom ordering (?ordering=total_spent|delivery_health|overdue_projects)
        - Default filtering (active projects from last 90 days when no filters applied)

        Returns:
            QuerySet: Annotated queryset with all necessary prefetching for performance
        """

        queryset = Client.objects.all()

        # Apply user permissions
        if not self.request.user.is_superuser:
            queryset = queryset.filter(manager=self.request.user)

        # Filter by status if provided
        status = self.request.query_params.get('status', None)
        if status:
            queryset = queryset.filter(projects__status=status)

        # Filter by min_budget if provided
        min_budget = self.request.query_params.get('min_budget', None)
        if min_budget:
            queryset = queryset.filter(projects__budget__gte=min_budget)

        # Filter by start_after date if provided
        start_after = self.request.query_params.get('start_after', None)
        if start_after:
            start_date = datetime.strptime(start_after, '%Y-%m-%d').date()
            queryset = queryset.filter(projects__start_date__gte=start_date)

        # Apply default filter for active projects in last 90 days if no specific filters
        if not any([status, min_budget, start_after]):
            queryset = queryset.filter(
                projects__start_date__gte=timezone.now() - timedelta(days=90),
                projects__status=ProjectStatusChoice.ACTIVE
            ).distinct()

        ordering = self.request.query_params.get('ordering', None)
        if ordering:
            if ordering == 'total_spent':
                queryset = queryset.annotate(
                    total_spent=Sum(
                        F('projects__tasks__billing_info__hours_worked') *
                        F('projects__tasks__billing_info__hourly_rate'),
                        filter=Q(projects__tasks__billing_info__is_billible=True)
                    )
                ).order_by('-total_spent')

            elif ordering == 'delivery_health':
                
                queryset = queryset.annotate(
                    completed_projects=Count(
                        'projects',
                        filter=Q(projects__status=ProjectStatusChoice.COMPLETED)
                    ),
                    on_time_projects=Count(
                        'projects',
                        filter=Q(
                            projects__status=ProjectStatusChoice.COMPLETED,
                            projects__actual_end_date__lte=F('projects__end_date')
                        )
                    )
                ).annotate(
                    health_percentage=Case(
                        When(completed_projects=0, then=Value(0)),
                        default=ExpressionWrapper(
                            100.0 * F('on_time_projects') / F('completed_projects'),
                            output_field=FloatField()
                        ),
                        output_field=FloatField()
                    )
                ).order_by('-health_percentage')

            elif ordering == 'overdue_projects':
                queryset = queryset.annotate(
                    overdue_count=Count(
                        'projects',
                        filter=Q(projects__status=ProjectStatusChoice.OVERDUE)
                    )
                ).order_by('-overdue_count')

        return queryset.prefetch_related(
            'projects__tasks',
            'projects__team',
            'projects__client',
            'projects__tasks__assigned_user'
        )

    @method_decorator(cache_page(60 * 15))
    def list(self, request, *args, **kwargs):

        export_format = request.query_params.get('format')

        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data

        if export_format == 'csv':
            return self.export_csv(data)

        return super().list(request, *args, **kwargs)

    def export_csv(self, data):
        """Export as CSV"""
        output = io.StringIO()
        writer = csv.writer(output)

        # Write headers
        if data:
            headers = [
                'Client Name', 'Total Projects', 'Total Budget', 'Total Amount Spent',
                'Overall Delivery Health', 'Overdue Projects', 'Top 3 Teams'
            ]
            writer.writerow(headers)

            # Write data
            for client in data:
                top_teams = ', '.join(
                    client.get('top_3_teams_by_average_task_delivery_speed_last_30_days') or []
                )
                writer.writerow([
                    client.get('name', ''),
                    client.get('total_projects', 0),
                    client.get('total_budget', 0),
                    client.get('total_amount_spent', 0),
                    client.get('overall_delivery_health', 0),
                    client.get('overdue_projects', 0),
                    top_teams
                ])

        output.seek(0)
        response = HttpResponse(
            output.getvalue(),
            content_type='text/csv',
            headers={"Content-Disposition": 'attachment; filename="client_health_report.csv"'},
        )

        return response
