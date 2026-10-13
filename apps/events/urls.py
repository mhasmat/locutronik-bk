from rest_framework.routers import DefaultRouter
from .views import VenueViewSet, EventViewSet

router = DefaultRouter()
router.register('venues', VenueViewSet, basename='venue')
router.register('', EventViewSet, basename='event')

urlpatterns = router.urls