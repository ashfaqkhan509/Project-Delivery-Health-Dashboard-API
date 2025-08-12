from rest_framework.test import APITestCase
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from health_delivery_app.models import (
    Client, Project, Task, UserBillingInfo, ProjectStatusChoice, Team, TaskStatusChoice
)


User = get_user_model()


class ProjectHealthViewSetTests(APITestCase):
    """
    Test suite for the ProjectHealthViewSet API endpoints.

    This class tests various aspects of the project health reporting functionality including:
    - Listing client projects with health metrics
    - Filtering by project status, budget, and start date
    - Ordering by different health metrics
    - CSV export functionality
    - Caching behavior

    The setUp method creates test data including:
    - An admin user for authentication
    - A client with manager
    - Multiple projects with different statuse and budgets
    - Tasks associated with projects
    - User billing information
    - Team assignments
    """

    def setUp(self):
        """Initialize test data and authenticate admin user."""
        self.url = "/api/clients/project-health/"

        # Create superuser and authenticate
        self.admin = User.objects.create_user(
            email="admin@gmail.com",
            password="pass",
            is_superuser=True
        )
        self.client.force_authenticate(user=self.admin)

        # Sample data
        now = timezone.now().date()
        manager = User.objects.create_user(email="manager@gmail.com", password="pass")
        billing_user = User.objects.create_user(email="testuser@gmail.com", password="pass")

        team = Team.objects.create(name="Test Team")
        client_obj = Client.objects.create(name="Test Client")

        project1 = Project.objects.create(
            name="P1",
            client=client_obj,
            team=team,
            budget=Decimal("10000.00"),
            status=ProjectStatusChoice.ACTIVE,
            start_date=now - timedelta(days=10)
        )

        project2 = Project.objects.create(
            name="P2",
            client=client_obj,
            team=team,
            budget=Decimal("20000.00"),
            status=ProjectStatusChoice.COMPLETED,
            start_date=now - timedelta(days=40),
            end_date=now - timedelta(days=5),
            actual_end_date=now - timedelta(days=5)
        )

        Task.objects.create(
            name="T1",
            project=project1,
            assigned_user=manager,
            status=TaskStatusChoice.DONE,
            start_date=now - timedelta(days=8),
            due_date=now - timedelta(days=3),
            actual_end_date=now - timedelta(days=2),
            total_hours_worked=Decimal("8.00")
        )

        Task.objects.create(
            name="T2",
            project=project2,
            assigned_user=billing_user,
            status=TaskStatusChoice.DONE,
            start_date=now - timedelta(days=35),
            due_date=now - timedelta(days=6),
            actual_end_date=now - timedelta(days=5),
            total_hours_worked=Decimal("10.00")
        )

        Task.objects.create(
            name="T3",
            project=project1,
            assigned_user=billing_user,
            status=TaskStatusChoice.IN_PROGRESS,
            start_date=now - timedelta(days=95),
            due_date=now - timedelta(days=15),
            total_hours_worked=Decimal("5.00")
        )

        Task.objects.create(
            name="T4",
            project=project2,
            assigned_user=manager,
            status=TaskStatusChoice.DONE,
            start_date=now - timedelta(days=4),
            due_date=now - timedelta(days=1),
            actual_end_date=now - timedelta(days=1),
            total_hours_worked=Decimal("12.00")
        )

        # Create billing info (OneToOne relationship with User)
        UserBillingInfo.objects.create(
            user=manager,
            hourly_rate=Decimal("150.00")
        )

        UserBillingInfo.objects.create(
            user=billing_user,
            hourly_rate=Decimal("100.00")
        )

        team.members.add(manager, billing_user)
        self.client_obj = client_obj

    def _get_results(self, resp):
        """Helper to extract 'results' from paginated response.

        Args:
            resp: The API response object

        Returns:
            The results list from paginated response or the entire data if not paginated
        """
        data = resp.json()
        return data.get("results", data)

    def test_list_clients(self):
        """Test basic listing of clients with project health data."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        results = self._get_results(response)
        self.assertIsInstance(results, list)
        self.assertIn("total_projects", results[0])

    def test_filter_by_status(self):
        """Test filtering projects by status."""
        response = self.client.get(self.url, {"status": ProjectStatusChoice.COMPLETED})
        self.assertEqual(response.status_code, 200)
        for client_data in self._get_results(response):
            projects = client_data.get("projects", [])
            self.assertTrue(any(
                project.get("status") == ProjectStatusChoice.COMPLETED for project in projects
            ))

    def test_filter_by_min_budget(self):
        """Test filtering projects by minimum budget."""
        response = self.client.get(self.url, {"min_budget": "15000"})
        self.assertEqual(response.status_code, 200)
        for client_data in self._get_results(response):
            projects = client_data.get("projects", [])
            self.assertTrue(any(
                float(project.get("budget", 0) or 0) >= 15000 for project in projects
            ))

    def test_filter_by_start_after(self):
        """Test filtering projects by start date."""
        start_after = (timezone.now() - timedelta(days=5)).date()
        response = self.client.get(self.url, {"start_after": str(start_after)})
        self.assertEqual(response.status_code, 200)
        for client_data in self._get_results(response):
            for project in client_data.get("projects", []):
                start_date = project.get("start_date")
                if start_date:
                    parsed = datetime.strptime(start_date, "%Y-%m-%d").date()
                    self.assertGreaterEqual(parsed, start_after)

    def test_order_by_total_spent(self):
        """Test ordering results by total spent amount."""
        response = self.client.get(self.url, {"ordering": "total_spent"})
        self.assertEqual(response.status_code, 200)

    def test_order_by_delivery_health(self):
        """Test ordering results by delivery health metric."""
        response = self.client.get(self.url, {"ordering": "delivery_health"})
        self.assertEqual(response.status_code, 200)

    def test_order_by_overdue_projects(self):
        """Test ordering results by number of overdue projects."""
        response = self.client.get(self.url, {"ordering": "overdue_projects"})
        self.assertEqual(response.status_code, 200)

    def test_csv_export(self):
        """Test CSV export functionality."""
        response = self.client.get(self.url, {"format": "csv"})
        self.assertEqual(response.status_code, 200)
        content_type = response.headers.get("Content-Type")
        self.assertIn("text/csv", content_type)
        content = response.content.decode()
        self.assertTrue("Client Name" in content)

    def test_cache_behavior(self):
        """Test that caching reduces database queries for subsequent requests."""
        with self.settings(
            CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
        ):
            cache.clear()

            with CaptureQueriesContext(connection) as first_request_queries:
                response_first = self.client.get(self.url)
            queries_first = len(first_request_queries)

            with CaptureQueriesContext(connection) as second_request_queries:
                response_second = self.client.get(self.url)
            queries_second = len(second_request_queries)

            self.assertEqual(response_first.content, response_second.content)

            self.assertLess(
                queries_second,
                queries_first
            )
