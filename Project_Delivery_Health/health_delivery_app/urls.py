from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProjectHealthViewSet, UserRegisterView, UserLoginView


router = DefaultRouter()
router.register(r'clients/project-health', ProjectHealthViewSet, basename='project-health')


urlpatterns = [
    # Authenthication
    path('auth/register/', UserRegisterView.as_view(), name="register"),
    path('auth/login/', UserLoginView.as_view(), name='login'),
    path('api/', include(router.urls)),
]
