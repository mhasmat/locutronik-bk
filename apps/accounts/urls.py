from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import RegisterView, RegisterProducerView, MeView


urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('register-producer/', RegisterProducerView.as_view(), name='register-producer'),
    path('login/', TokenObtainPairView.as_view(), name='login'),
    path('refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('me/', MeView.as_view(), name='me'),
]