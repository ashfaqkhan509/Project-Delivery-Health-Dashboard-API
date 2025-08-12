from django.test import TestCase
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from health_delivery_app.models import (
    Team,
    Task,
    Project,
    Client,
    ProjectStatusChoice,
    TaskStatusChoice
)
from health_delivery_app.tasks import recompute_delivery_velocity
from django.contrib.auth import get_user_model


User = get_user_model()


class RecomputeDeliveryVelocityTaskTests(TestCase):
    def setUp(self):
        cache.clear()
        self.today = timezone.now().date()

        self.user = User.objects.create_user(email="testuser@gmail.com", password="pass")

        self.client_obj = Client.objects.create(name="Test Client")

        self.team = Team.objects.create(name="Test Team")

        self.project = Project.objects.create(
            name="Test Project",
            client=self.client_obj,
            team=self.team,
            budget=Decimal("5000.00"),
            status=ProjectStatusChoice.ACTIVE,
            start_date=self.today - timedelta(days=10)
        )

        Task.objects.create(
            name="T1",
            project=self.project,
            assigned_user=self.user,
            status=TaskStatusChoice.DONE,
            start_date=self.today - timedelta(days=35),
            due_date=self.today - timedelta(days=5),
            actual_end_date=self.today - timedelta(days=3),
            total_hours_worked=Decimal("8.00")
        )

        Task.objects.create(
            name="T2",
            project=self.project,
            assigned_user=self.user,
            status=TaskStatusChoice.DONE,
            start_date=self.today - timedelta(days=40),
            due_date=self.today - timedelta(days=15),
            actual_end_date=self.today - timedelta(days=10),
            total_hours_worked=Decimal("10.00")
        )

        Task.objects.create(
            name="T3",
            project=self.project,
            assigned_user=self.user,
            status=TaskStatusChoice.IN_PROGRESS,
            start_date=self.today - timedelta(days=50),
            due_date=self.today - timedelta(days=40),
            actual_end_date=self.today - timedelta(days=35),
            total_hours_worked=Decimal("5.00")
        )

    def test_recompute_delivery_velocity(self):

        message = recompute_delivery_velocity()

        self.assertIn("Recomputed velocities for", message)

        # Check cache contents
        velocities = cache.get("team_velocities")
        self.assertIsNotNone(velocities)
        self.assertIn(self.team.id, velocities)

        # 2 tasks in last 30 days → velocity = 2 / 30
        expected_velocity = 2 / 30.0
        self.assertAlmostEqual(velocities[self.team.id], expected_velocity, places=4)
