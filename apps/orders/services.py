from decimal import Decimal
from datetime import timedelta
import secrets
import threading

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.events.models import Event, TicketType, PlatformConfig
from .models import Order, Ticket

RESERVATION_MINUTES = 20

def _generate_qr_token():
    return secrets.token_urlsafe(32)

def _calculate_fee(price, fee_percent):
    return (price * fee_percent / Decimal('100')).quantize(Decimal('0.01'))

def _send_email_async(order_id):
    from apps.orders.tasks import send_purchase_confirmation
    try:
        send_purchase_confirmation.__wrapped__(str(order_id))
        Order.objects.filter(id=order_id).update(email_sent=True)
        print(f"[EMAIL] Enviado para orden {order_id}")
    except Exception as e:
        print(f"[EMAIL] Error en orden {order_id}: {e}")

def create_order(user, event_id, items):
    try:
        event = Event.objects.get(id=event_id, status='published')
    except Event.DoesNotExist:
        return None, "Evento no encontrado o no está publicado."

    now = timezone.now()
    if now < event.sale_start_time:
        return None, "La venta todavía no comenzó."
    if now > event.sale_end_time:
        return None, "La venta ya finalizó."

    if not items:
        return None, "Debés seleccionar al menos un ticket."

    tt_ids = [item['ticket_type'] for item in items]
    if len(tt_ids) != len(set(tt_ids)):
        return None, "Hay tipos de ticket repetidos en la orden."

    # Obtenemos la configuración global por si el evento no tiene una definida
    global_config = PlatformConfig.objects.first()
    if not global_config:
        global_config = PlatformConfig.objects.create(fee_type='percentage', fee_value=8.00)

    with transaction.atomic():
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
                return None, f"No hay suficientes entradas para '{tt.name}'. Disponibles: {tt.quantity_available}."

            tt.quantity_available -= qty
            tt.save(update_fields=['quantity_available'])

            # 👇 LÓGICA DE FEE POR EVENTO (CON FALLBACK AL GLOBAL)
            fee_type = getattr(event, 'fee_type', 'percentage')
            fee_value = getattr(event, 'fee_value', global_config.fee_value)

            if fee_type == 'percentage':
                fee_per_ticket = _calculate_fee(tt.price, fee_value)
            else:
                fee_per_ticket = fee_value

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
            expires_at=now + timedelta(minutes=RESERVATION_MINUTES),
            items_snapshot=items_snapshot,
        )

        return order, None

def confirm_order_payment(order, payment_provider='', payment_reference=''):
    with transaction.atomic():
        order = Order.objects.select_for_update().get(id=order.id)

        if order.status != 'pending':
            return False

        order.status = 'paid'
        order.paid_at = timezone.now()
        order.payment_provider = payment_provider
        order.payment_reference = payment_reference
        order.save(update_fields=['status', 'paid_at', 'payment_provider', 'payment_reference'])

        ticket_types = {
            tt.id: tt for tt in TicketType.objects.filter(
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
    with transaction.atomic():
        order = Order.objects.select_for_update().get(id=order.id)

        if order.status != 'pending':
            return False

        for item in order.items_snapshot:
            TicketType.objects.filter(id=item['ticket_type_id']).update(
                quantity_available=F('quantity_available') + item['quantity']
            )

        order.status = new_status
        order.save(update_fields=['status'])
        return True