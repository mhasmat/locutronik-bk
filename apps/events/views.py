from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Venue, Event, TicketType
from .serializers import (
    VenueSerializer, EventListSerializer, EventDetailSerializer,
    EventCreateUpdateSerializer, TicketTypeSerializer
)
from .permissions import IsProducerOrReadOnly


class VenueViewSet(viewsets.ModelViewSet):
    queryset = Venue.objects.all()
    serializer_class = VenueSerializer
    permission_classes = [IsProducerOrReadOnly]


class EventViewSet(viewsets.ModelViewSet):
    permission_classes = [IsProducerOrReadOnly]

    def get_queryset(self):
        qs = Event.objects.select_related('venue', 'organizer').prefetch_related('ticket_types')

        user = self.request.user

        # Vista privada (mis eventos)
        if self.action == 'list' and self.request.query_params.get('mine') == 'true':
            if not user.is_authenticated:
                return qs.none()
            return qs.filter(organizer=user)

        # Detalle: el dueño puede ver cualquier estado; el resto solo publicados
        if self.action == 'retrieve':
            if user.is_authenticated:
                # Devolver publicados + los propios (aunque estén en draft)
                from django.db.models import Q
                return qs.filter(Q(status='published') | Q(organizer=user))
            return qs.filter(status='published')

        # Listado público
        if self.action == 'list':
            return qs.filter(status='published')

        return qs
    

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return EventCreateUpdateSerializer
        if self.action == 'retrieve':
            return EventDetailSerializer
        return EventListSerializer

    def perform_create(self, serializer):
        serializer.save(organizer=self.request.user)

    def perform_update(self, serializer):
        # Solo el dueño puede editar (el queryset ya filtra, pero doble check)
        if serializer.instance.organizer != self.request.user:
            raise permissions.PermissionDenied('No sos el dueño de este evento.')
        serializer.save()

    @action(detail=True, methods=['get'], permission_classes=[permissions.AllowAny])
    def ticket_types(self, request, pk=None):
        """Listado público de tipos de ticket del evento."""
        event = self.get_object()
        tts = event.ticket_types.filter(is_active=True)
        return Response(TicketTypeSerializer(tts, many=True).data)