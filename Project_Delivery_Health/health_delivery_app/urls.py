from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProjectHealthViewSet


router = DefaultRouter()
router.register(r'clients/project-health', ProjectHealthViewSet, basename='project-health')


urlpatterns = [
    path('api/', include(router.urls)),
]
