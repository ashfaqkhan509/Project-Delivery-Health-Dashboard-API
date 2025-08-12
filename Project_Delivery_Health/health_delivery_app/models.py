from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone


class CustomUserManager(BaseUserManager):
    """
    Manager for CustomUser model using email as the unique identifier.
    """
    def create_user(self, email, password=None, **extra_fields):
        """
        Create and save a regular user with the given email and password.
        """
        if not email:
            raise ValueError("Users must have an email address")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """
        Create and save a superuser with the given email and password.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractBaseUser, PermissionsMixin):
    """
    Custom user model that uses email instead of username for authentication.
    """
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=30, blank=True)
    is_manager = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email


class ProjectStatusChoice(models.TextChoices):
    """
    Choices for the status of a project.
    """
    ACTIVE = "active", "Active"
    COMPLETED = "completed", "Completed"
    OVERDUE = "overdue", "Overdue"


class TaskStatusChoice(models.TextChoices):
    """
    Choices for the status of a task.
    """
    IN_PROGRESS = "in_progress", "In Progress"
    REVIEW = "review", "In Review"
    DONE = "done", "Done"


class Client(models.Model):
    """
    Represents a client for whom projects are undertaken.
    """
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class Team(models.Model):
    """
    Represents a team of users working on projects.
    """
    name = models.CharField(max_length=255)
    members = models.ManyToManyField(CustomUser, related_name='teams')

    def __str__(self):
        return self.name


class Project(models.Model):
    """
    Represents a project assigned to a team for a client.
    """
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name='projects',
        blank=True,
        null=True
    )
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='projects')
    budget = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=ProjectStatusChoice.choices,
        default=ProjectStatusChoice.ACTIVE
    )
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    actual_end_date = models.DateField(blank=True, null=True)

    def __str__(self):
        return self.name


class Task(models.Model):
    """
    Represents a task within a project assigned to a user.
    """
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='tasks')
    assigned_user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='tasks',
        blank=True,
        null=True
    )
    status = models.CharField(
        max_length=20,
        choices=TaskStatusChoice.choices,
        default=TaskStatusChoice.IN_PROGRESS
    )
    start_date = models.DateField()
    due_date = models.DateField(blank=True, null=True)
    actual_end_date = models.DateField(blank=True, null=True)
    total_hours_worked = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return self.name


class UserBillingInfo(models.Model):
    """
    Stores billing information for a user, including hourly rate.
    """
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='billing_info')
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} billing info"
