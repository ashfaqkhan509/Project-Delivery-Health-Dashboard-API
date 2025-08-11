import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Project_Delivery_Health.settings')

app = Celery('Project_Delivery_Health')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
