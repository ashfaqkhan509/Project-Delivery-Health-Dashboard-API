from rest_framework.test import APITestCase
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal
from django.core.cache import cache
from django.contrib.auth import get_user_model

from health_delivery_app.models import (
    Client, Project, Task, UserBillingInfo, ProjectStatusChoice, Team
)


User = get_user_model()


class ProjectHealthViewSetTests(APITestCase):
    def setUp(self):
        self.url = "/api/clients/project-health/"

        # Create superuser and authenticate
        self.admin = User.objects.create_user(
            username="admin",
            password="pass",
            is_superuser=True
        )
        self.client.force_authenticate(user=self.admin)

        # Sample data
        now = timezone.now().date()
        manager = User.objects.create_user(username="manager", password="pass")
        billing_user = User.objects.create_user(username="billuser", password="pass")

        team = Team.objects.create(name="Alpha Team")
        client_obj = Client.objects.create(name="Test Client", manager=manager)

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
            status=ProjectStatusChoice.COMPLETED,
            due_date=now - timedelta(days=3),
            actual_end_date=now - timedelta(days=2)
        )

        task2 = Task.objects.create(
            name="T2",
            project=project2,
            assigned_user=manager,
            status=ProjectStatusChoice.COMPLETED,
            due_date=now - timedelta(days=6),
            actual_end_date=now - timedelta(days=5)
        )

        UserBillingInfo.objects.create(
            user=billing_user,
            task=task2,
            hours_worked=Decimal("10.00"),
            hourly_rate=Decimal("100.00"),
            is_billible=True
        )

        team.members.add(manager, billing_user)
        self.client_obj = client_obj

    def _get_results(self, resp):
        """Helper to extract 'results' from paginated response"""
        data = resp.json()
        return data.get("results", data)

    def test_list_clients(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        results = self._get_results(resp)
        self.assertIsInstance(results, list)
        self.assertIn("total_projects", results[0])

    def test_filter_by_status(self):
        resp = self.client.get(self.url, {"status": ProjectStatusChoice.COMPLETED})
        self.assertEqual(resp.status_code, 200)
        for client_data in self._get_results(resp):
            projects = client_data.get("projects", [])
            self.assertTrue(any(
                project.get("status") == ProjectStatusChoice.COMPLETED for project in projects
            ))

    def test_filter_by_min_budget(self):
        resp = self.client.get(self.url, {"min_budget": "15000"})
        self.assertEqual(resp.status_code, 200)
        for client_data in self._get_results(resp):
            projects = client_data.get("projects", [])
            self.assertTrue(any(
                float(project.get("budget", 0) or 0) >= 15000 for project in projects
            ))

    def test_filter_by_start_after(self):
        start_after = (timezone.now() - timedelta(days=5)).date()
        resp = self.client.get(self.url, {"start_after": str(start_after)})
        self.assertEqual(resp.status_code, 200)
        for client_data in self._get_results(resp):
            for project in client_data.get("projects", []):
                start_date = project.get("start_date")
                if start_date:
                    parsed = datetime.strptime(start_date, "%Y-%m-%d").date()
                    self.assertGreaterEqual(parsed, start_after)

    def test_order_by_total_spent(self):
        resp = self.client.get(self.url, {"ordering": "total_spent"})
        self.assertEqual(resp.status_code, 200)

    def test_order_by_delivery_health(self):
        resp = self.client.get(self.url, {"ordering": "delivery_health"})
        self.assertEqual(resp.status_code, 200)

    def test_order_by_overdue_projects(self):
        resp = self.client.get(self.url, {"ordering": "overdue_projects"})
        self.assertEqual(resp.status_code, 200)

    def test_csv_export(self):
        resp = self.client.get(self.url, {"format": "csv"})
        self.assertEqual(resp.status_code, 200)
        content_type = resp.headers.get("Content-Type")
        self.assertIn("text/csv", content_type)
        content = resp.content.decode()
        self.assertTrue("Client Name" in content)

    def test_cache_behavior(self):
        with self.settings(
            CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
        ):
            cache.clear()
            first = self.client.get(self.url)
            second = self.client.get(self.url)
            self.assertEqual(first.content, second.content)
