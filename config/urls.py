from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from apps.orders.cron_views import (
    ExpireOrdersCronView,
    SyncMpPaymentsCronView,
    SendPendingEmailsCronView,
)

urlpatterns = [
    path('admin/', admin.site.urls),

    path('api/auth/', include('apps.accounts.urls')),
    path('api/events/', include('apps.events.urls')),
    path('api/orders/', include('apps.orders.urls')),
    path('api/payments/', include('apps.payments.urls')),
    path('api/reports/', include('apps.reports.urls')),

    path('api/cron/expire-orders/', ExpireOrdersCronView.as_view()),
    path('api/cron/sync-mp-payments/', SyncMpPaymentsCronView.as_view()),
    path('api/cron/send-pending-emails/', SendPendingEmailsCronView.as_view()),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
                                                                          