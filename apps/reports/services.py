from decimal import Decimal
from django.db.models import Sum, Count, Q, F, Avg

from apps.events.models import Event, TicketType
from apps.orders.models import Order, Ticket


def get_event_or_none(event_id, user):
    """
    Devuelve el evento si el usuario es su organizador, o None si no existe/permiso.
    """
    return Event.objects.filter(id=event_id, organizer=user).first()


def build_event_summary(event):
    """
    Arma el resumen completo del evento.
    Solo cuenta tickets de órdenes 'paid'.
    """
    # Tickets vendidos (solo pagados)
    paid_tickets = Ticket.objects.filter(
        order__event=event,
        order__status='paid',
    )

    tickets_sold = paid_tickets.count()
    gross_revenue = paid_tickets.aggregate(total=Sum('price'))['total'] or Decimal('0')
    platform_fee = paid_tickets.aggregate(total=Sum('fee'))['total'] or Decimal('0')

    # Órdenes
    orders_paid = Order.objects.filter(event=event, status='paid').count()
    orders_pending = Order.objects.filter(event=event, status='pending').count()

    # Stock
    ticket_types = event.ticket_types.all().order_by('id')

    tickets_total = sum(tt.quantity_total for tt in ticket_types)
    tickets_available = sum(tt.quantity_available for tt in ticket_types)

    # Detalle por tipo de ticket
    per_type_data = []
    for tt in ticket_types:
        tt_sold_qs = paid_tickets.filter(ticket_type=tt)
        tt_sold = tt_sold_qs.count()
        tt_gross = tt_sold_qs.aggregate(total=Sum('price'))['total'] or Decimal('0')
        tt_fee = tt_sold_qs.aggregate(total=Sum('fee'))['total'] or Decimal('0')

        per_type_data.append({
            'ticket_type_id': tt.id,
            'name': tt.name,
            'price': tt.price,
            'quantity_total': tt.quantity_total,
            'quantity_sold': tt_sold,
            'quantity_available': tt.quantity_available,
            'gross_revenue': tt_gross,
            'platform_fee': tt_fee,
        })

    return {
        'event_id': event.id,
        'event_name': event.name,
        'event_start': event.start_time,
        'status': event.status,
        'tickets_sold': tickets_sold,
        'tickets_available': tickets_available,
        'tickets_total': tickets_total,
        'gross_revenue': gross_revenue,
        'platform_fee': platform_fee,
        'net_to_organizer': gross_revenue,
        'orders_paid': orders_paid,
        'orders_pending': orders_pending,
        'ticket_types': per_type_data,
    }


def build_sales_queryset(event, filters=None):
    """
    Devuelve el queryset de tickets vendidos, con filtros opcionales.
    """
    qs = (
        Ticket.objects
        .filter(order__event=event, order__status='paid')
        .select_related('order', 'order__user', 'ticket_type')
        .order_by('-sold_at')
    )

    if not filters:
        return qs

    # Filtro por tipo de ticket
    ticket_type_id = filters.get('ticket_type')
    if ticket_type_id:
        qs = qs.filter(ticket_type_id=ticket_type_id)

    # Filtro por estado
    status_filter = filters.get('status')
    if status_filter in ('valid', 'used', 'cancelled'):
        qs = qs.filter(status=status_filter)

    # Filtro por rango de fechas
    date_from = filters.get('date_from')
    if date_from:
        qs = qs.filter(sold_at__gte=date_from)

    date_to = filters.get('date_to')
    if date_to:
        qs = qs.filter(sold_at__lte=date_to)

    return qs


def build_payout(event):
    """
    Cálculo de liquidación final.
    El productor recibe gross_revenue - platform_fee = net_to_organizer.
    """
    paid_tickets = Ticket.objects.filter(
        order__event=event,
        order__status='paid',
    )

    gross = paid_tickets.aggregate(total=Sum('price'))['total'] or Decimal('0')
    fee = paid_tickets.aggregate(total=Sum('fee'))['total'] or Decimal('0')
    tickets_sold = paid_tickets.count()

    avg_price = (gross / tickets_sold).quantize(Decimal('0.01')) if tickets_sold else Decimal('0')

    # Acá podríamos restar la comisión de Mercado Pago si quisiéramos ser
    # más finos. Por ahora la dejamos en 0, pero el campo ya está en el serializer.
    mp_fee = Decimal('0')

    net = gross - mp_fee

    return {
        'event_id': event.id,
        'event_name': event.name,
        'gross_revenue': gross,
        'platform_fee': fee,
        'net_to_organizer': net,
        'tickets_sold': tickets_sold,
        'average_ticket_price': avg_price,
        'mp_processing_fee': mp_fee,
        'final_payout': net,
    }