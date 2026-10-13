from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from rest_framework.pagination import PageNumberPagination

from .serializers import (
    EventSummarySerializer, TicketSaleSerializer, PayoutSerializer
)
from .services import (
    get_event_or_none, build_event_summary, build_sales_queryset, build_payout
)


class EventSummaryView(APIView):
    """
    GET /api/reports/events/<event_id>/summary/
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, event_id):
        event = get_event_or_none(event_id, request.user)
        if not event:
            return Response(
                {'detail': 'Evento no encontrado o no sos el organizador.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        data = build_event_summary(event)
        return Response(EventSummarySerializer(data).data)


class SalesPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


class EventSalesView(APIView):
    """
    GET /api/reports/events/<event_id>/sales/
    Query params opcionales:
      - ticket_type: id
      - status: valid | used | cancelled
      - date_from: ISO date
      - date_to: ISO date
      - page, page_size
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, event_id):
        event = get_event_or_none(event_id, request.user)
        if not event:
            return Response(
                {'detail': 'Evento no encontrado o no sos el organizador.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        filters = {
            'ticket_type': request.query_params.get('ticket_type'),
            'status': request.query_params.get('status'),
            'date_from': request.query_params.get('date_from'),
            'date_to': request.query_params.get('date_to'),
        }

        qs = build_sales_queryset(event, filters)

        paginator = SalesPagination()
        page = paginator.paginate_queryset(qs, request)

        # Convertimos a mano porque no es un ModelSerializer
        serialized = [
            {
                'ticket_id': t.id,
                'order_id': t.order_id,
                'ticket_type': t.ticket_type.name,
                'price': t.price,
                'fee': t.fee,
                'status': t.status,
                'buyer_username': t.order.user.username,
                'sold_at': t.sold_at,
                'used_at': t.used_at,
            }
            for t in page
        ]

        return paginator.get_paginated_response(
            TicketSaleSerializer(serialized, many=True).data
        )


class EventPayoutView(APIView):
    """
    GET /api/reports/events/<event_id>/payout/
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, event_id):
        event = get_event_or_none(event_id, request.user)
        if not event:
            return Response(
                {'detail': 'Evento no encontrado o no sos el organizador.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        data = build_payout(event)
        return Response(PayoutSerializer(data).data)