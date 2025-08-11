from django.db import models
from django.contrib.auth.models import User


class ProjectStatusChoice(models.TextChoices):
    ACTIVE = "active", "Active"
    COMPLETED = "completed", "Completed"
    OVERDUE = "overdue", "Overdue"


class Client(models.Model):
    name = models.CharField(max_length=255)
    manager = models.ForeignKey(User, on_delete=models.CASCADE, related_name='managed_clients')

    def __str__(self):
        return self.name
    

class Team(models.Model):
    name = models.CharField(max_length=255)
    members = models.ManyToManyField(User, related_name='teams')

    def __str__(self):
        return self.name
    

class Project(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='projects', blank=True, null=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='projects')
    budget = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    status = models.CharField(
        max_length=10,
        choices=ProjectStatusChoice.choices,
        default=ProjectStatusChoice.ACTIVE
    )
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    actual_end_date = models.DateField(blank=True, null=True)

    def __str__(self):
        return self.name


class Task(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='tasks')
    assigned_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tasks', blank=True, null=True)
    status = models.CharField(
        max_length=10,
        choices=ProjectStatusChoice.choices,
        default=ProjectStatusChoice.ACTIVE
    )
    due_date = models.DateField(blank=True, null=True)
    actual_end_date = models.DateField(blank=True, null=True)

    def __str__(self):
        return self.name
    

class UserBillingInfo(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='billing_info')
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='billing_info', blank=True, null=True)
    hours_worked = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_billible = models.BooleanField(default=True)
    date = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.date}"
    
    @property
    def total_billing(self):
        return self.hours_worked * self.hourly_rate
