import threading
from django.db import transaction

from decimal import Decimal
from datetime import timedelta

from django.db import transaction
from django.db.models import F
from django.utils import timezone
import secrets
from django.conf import settings

from apps.events.models import Event, TicketType
from .models import Order, Ticket


def _generate_qr_token():
    """Genera un token único para el QR del ticket."""
    return secrets.token_urlsafe(32)


def _calculate_fee(price, fee_percent):
    """Calcula el fee por ticket, redondeado a 2 decimales."""
    return (price * fee_percent / Decimal('100')).quantize(Decimal('0.01'))


def create_order(user, event_id, items):
    """
    Crea una orden pending y reserva stock en DB de forma atómica.

    items: lista de dicts [{'ticket_type': <id>, 'quantity': <int>}, ...]

    Retorna (order, error_message). Si hay error, order es None.
    """
    try:
        event = Event.objects.get(id=event_id, status='published')
    except Event.DoesNotExist:
        return None, "Evento no encontrado o no está publicado."

    now = timezone.now()
    if now < event.sale_start_time:
        return None, "La venta todavía no comenzó."
    if now > event.sale_end_time:
        return None, "La venta ya finalizó."

    # Validación básica de items
    if not items:
        return None, "Debés seleccionar al menos un ticket."

    tt_ids = [item['ticket_type'] for item in items]
    if len(tt_ids) != len(set(tt_ids)):
        return None, "Hay tipos de ticket repetidos en la orden."

    with transaction.atomic():
        # Bloqueamos los TicketType ordenados por id para evitar deadlocks
        locked = (
            TicketType.objects
            .select_for_update()
            .filter(id__in=sorted(tt_ids), event=event, is_active=True)
        )
        ticket_types = {tt.id: tt for tt in locked}

        if len(ticket_types) != len(tt_ids):
            return None, "Alguno de los tipos de ticket no existe, no pertenece al evento o no está activo."

        subtotal = Decimal('0')
        fee_total = Decimal('0')
        items_snapshot = []

        for item in items:
            tt = ticket_types[item['ticket_type']]
            qty = item['quantity']

            if qty < 1:
                return None, f"Cantidad inválida para '{tt.name}'."
            if qty > tt.max_per_user:
                return None, f"Máximo {tt.max_per_user} por usuario para '{tt.name}'."
            if tt.quantity_available < qty:
                return None, (
                    f"No hay suficientes entradas para '{tt.name}'. "
                    f"Disponibles: {tt.quantity_available}."
                )

            # Descontamos el stock (reserva)
            tt.quantity_available -= qty
            tt.save(update_fields=['quantity_available'])

            fee_per_ticket = _calculate_fee(tt.price, event.platform_fee_percent)

            subtotal += tt.price * qty
            fee_total += fee_per_ticket * qty

            items_snapshot.append({
                'ticket_type_id': tt.id,
                'ticket_type_name': tt.name,
                'quantity': qty,
                'price': str(tt.price),
                'fee': str(fee_per_ticket),
            })

        order = Order.objects.create(
            user=user,
            event=event,
            subtotal=subtotal,
            platform_fee=fee_total,
            total_amount=subtotal + fee_total,
            status='pending',
            expires_at=now + timedelta(minutes=settings.RESERVATION_MINUTES),
            items_snapshot=items_snapshot,
        )

        return order, None


def _send_email_async(order_id):
    """Envía el email en un hilo aparte para no bloquear."""
    from apps.orders.tasks import send_purchase_confirmation
    try:
        send_purchase_confirmation.__wrapped__(str(order_id))
        # Marcamos como enviado
        Order.objects.filter(id=order_id).update(email_sent=True)
        print(f"[EMAIL] Enviado para orden {order_id}")
    except Exception as e:
        print(f"[EMAIL] Error en orden {order_id}: {e}")

def confirm_order_payment(order, payment_provider='', payment_reference=''):
    """
    Marca la orden como pagada y genera los tickets con sus QRs.
    Llamado desde el webhook de la pasarela (próximo paso).
    """
    with transaction.atomic():
        order = Order.objects.select_for_update().get(id=order.id)

        if order.status != 'pending':
            return False

        order.status = 'paid'
        order.paid_at = timezone.now()
        order.payment_provider = payment_provider
        order.payment_reference = payment_reference
        order.save(update_fields=[
            'status', 'paid_at', 'payment_provider', 'payment_reference'
        ])

        # Generamos un Ticket por cada unidad
        ticket_types = {
            tt.id: tt
            for tt in TicketType.objects.filter(
                id__in=[i['ticket_type_id'] for i in order.items_snapshot]
            )
        }

        tickets_to_create = []
        for item in order.items_snapshot:
            tt = ticket_types[item['ticket_type_id']]
            for _ in range(item['quantity']):
                tickets_to_create.append(Ticket(
                    order=order,
                    ticket_type=tt,
                    price=Decimal(item['price']),
                    fee=Decimal(item['fee']),
                    qr_code=_generate_qr_token(),
                    status='valid',
                ))

        Ticket.objects.bulk_create(tickets_to_create)

                # Enviar email en segundo plano (después de que la transacción se confirme)
        order_id = order.id
        transaction.on_commit(
            lambda: threading.Thread(
                target=_send_email_async,
                args=(order_id,),
                daemon=True,
            ).start()
        )                

        return True        


def cancel_order(order, new_status='cancelled'):
    """
    Cancela una orden pending y devuelve el stock a los TicketTypes.
    """
    with transaction.atomic():
        order = Order.objects.select_for_update().get(id=order.id)

        if order.status != 'pending':
            return False

        # Devolvemos el stock
        for item in order.items_snapshot:
            TicketType.objects.filter(id=item['ticket_type_id']).update(
                quantity_available=F('quantity_available') + item['quantity']
            )

        order.status = new_status
        order.save(update_fields=['status'])
        return True


from .tasks import send_purchase_confirmation