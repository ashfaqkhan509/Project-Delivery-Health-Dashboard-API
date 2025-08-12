from rest_framework import viewsets
from health_delivery_app.models import Client, ProjectStatusChoice, CustomUser
from health_delivery_app.serializers import (
    ClientSerializer,
    UserSerializer,
    UserLoginSerializer,
    RegisterSerializer
)
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
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate


class UserRegisterView(generics.CreateAPIView):
    """
    API endpoint that allows new users to register.

    Creates a new user instance with the provided credentials.
    Returns the created user data and a success message.
    """
    queryset = CustomUser.objects.all()  # Changed from User to CustomUser
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        response_data = {
            "message": "User registered successfully",
            "user": UserSerializer(user).data
        }
        return Response(
            response_data,
            status=status.HTTP_201_CREATED
        )


class UserLoginView(APIView):
    """
    API endpoint for user authentication.

    Accepts email and password credentials.
    Returns JWT tokens (access and refresh) upon successful authentication.
    """
    def post(self, request, *args, **kwargs):
        serializer = UserLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        password = serializer.validated_data['password']

        # Authenticate using email instead of username
        user = authenticate(request, email=email, password=password)

        if user is None:
            return Response(
                {"error": "Invalid credentials."},
                status=status.HTTP_401_UNAUTHORIZED
            )

        refresh_token = RefreshToken.for_user(user)

        response_data = {
            "user": UserSerializer(user).data,
            "refresh": str(refresh_token),
            "access": str(refresh_token.access_token),
            "message": "Login successful."
        }
        return Response(
            response_data,
            status=status.HTTP_200_OK
        )


class ProjectHealthViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ClientSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [OrderingFilter]

    def get_queryset(self):
        queryset = Client.objects.all()
        user = self.request.user

        if not user.is_superuser:
            if user.is_manager:
                queryset = queryset.filter(
                    projects__team__members=user
                ).distinct()
            else:
                queryset = queryset.none()

        # Filter by project status
        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(projects__status=status)

        # Filter by minimum budget
        min_budget = self.request.query_params.get('min_budget')
        if min_budget:
            queryset = queryset.filter(projects__budget__gte=min_budget)

        # Filter by start date
        start_after = self.request.query_params.get('start_after')
        if start_after:
            start_date = datetime.strptime(start_after, '%Y-%m-%d').date()
            queryset = queryset.filter(projects__start_date__gte=start_date)

        # Default: active projects in last 90 days
        if not any([status, min_budget, start_after]):
            queryset = queryset.filter(
                projects__start_date__gte=timezone.now().date() - timedelta(days=90),
                projects__status=ProjectStatusChoice.ACTIVE
            ).distinct()

        # Ordering
        ordering = self.request.query_params.get('ordering')
        if ordering == 'total_spent':
            queryset = queryset.annotate(
                total_spent=Sum(
                    F('projects__tasks__total_hours_worked') *
                    F('projects__tasks__assigned_user__billing_info__hourly_rate'),
                    filter=Q(projects__tasks__assigned_user__billing_info__isnull=False)
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
            'projects__tasks__assigned_user__billing_info',
            'projects__team',
            'projects__client'
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

        if data:
            headers = [
                'Client Name', 'Total Projects', 'Total Budget', 'Total Amount Spent',
                'Overall Delivery Health', 'Overdue Projects', 'Top 3 Teams'
            ]
            writer.writerow(headers)

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
        return HttpResponse(
            output.getvalue(),
            content_type='text/csv',
            headers={"Content-Disposition": 'attachment; filename=\"client_health_report.csv\"'},
        )
