from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import ChangePasswordView, ProfileView, RegisterView, RegisterProducerView


urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('register-producer/', RegisterProducerView.as_view(), name='register-producer'),
    path('login/', TokenObtainPairView.as_view(), name='login'),
    path('refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    
    path('me/', ProfileView.as_view(), name='profile'), # Reemplaza o agrega si ya tenías la vista de obtener
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
]