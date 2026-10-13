from django.urls import path
from .views import EventSummaryView, EventSalesView, EventPayoutView


urlpatterns = [
    path(
        'events/<int:event_id>/summary/',
        EventSummaryView.as_view(),
        name='event-summary',
    ),
    path(
        'events/<int:event_id>/sales/',
        EventSalesView.as_view(),
        name='event-sales',
    ),
    path(
        'events/<int:event_id>/payout/',
        EventPayoutView.as_view(),
        name='event-payout',
    ),
]