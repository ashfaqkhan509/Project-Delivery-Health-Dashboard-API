from celery import shared_task
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
from .models import Team, Task, TaskStatusChoice


@shared_task
def recompute_delivery_velocity():
    """
    Background task to recompute team delivery velocities weekly
    """
    thirty_days_ago = timezone.now().date() - timedelta(days=30)

    teams = Team.objects.all()
    velocity_data = {}

    for team in teams:
        completed_tasks = Task.objects.filter(
            project__team=team,
            status=TaskStatusChoice.DONE,
            actual_end_date__gte=thirty_days_ago
        ).count()

        velocity = completed_tasks / 30.0
        velocity_data[team.id] = velocity

    # Cache the computed velocities
    cache.set('team_velocities', velocity_data, 60 * 60 * 24 * 7)

    return f"Recomputed velocities for {len(teams)} teams"
