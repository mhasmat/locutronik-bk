import io
from email.mime.application import MIMEApplication
from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.db.models import F
from .models import Order
from .services import cancel_order
from .ticket_image import generate_ticket_image


@shared_task(name='apps.orders.tasks.expire_pending_orders')
def expire_pending_orders():
    """
    Expira órdenes pending vencidas y devuelve el stock.
    Se ejecuta cada minuto vía Celery Beat.
    """
    now = timezone.now()
    expired_qs = Order.objects.filter(status='pending', expires_at__lt=now)

    count = 0
    for order in expired_qs.iterator():
        if cancel_order(order, new_status='expired'):
            count += 1

    return f"{count} órdenes expiradas."


@shared_task(name='apps.orders.tasks.send_purchase_confirmation', bind=True, max_retries=3)
def send_purchase_confirmation(self, order_id):
    """
    Envía el email de confirmación de compra con las entradas en PDF adjuntas.
    """
    try:
        order = Order.objects.select_related(
            'user', 'event', 'event__venue'
        ).prefetch_related('tickets__ticket_type').get(id=order_id)
    except Order.DoesNotExist:
        return f"Orden {order_id} no existe."

    if order.status != 'paid':
        return f"Orden {order_id} no está pagada."

    if not order.user.email:
        return f"Usuario {order.user.username} no tiene email."

    tickets = list(order.tickets.all())

    ctx = {
        'order': order,
        'event': order.event,
        'buyer_name': order.user.get_full_name() or order.user.username,
        'tickets': tickets,
    }
    subject = f"Tus entradas para {order.event.name}"
    text_body = render_to_string('orders/emails/purchase_confirmation.txt', ctx)
    html_body = render_to_string('orders/emails/purchase_confirmation.html', ctx)

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[order.user.email],
    )
    msg.attach_alternative(html_body, 'text/html')

    # --- Generar y adjuntar PDF de cada ticket ---
    for ticket in tickets:
        try:
            # generamos la imagen completa en PDF
            pdf_bytes = generate_ticket_image(ticket)

            # adjuntamos el PDF al email
            mime_pdf = MIMEApplication(pdf_bytes, _subtype='pdf')
            mime_pdf.add_header(
                'Content-Disposition',
                'attachment',
                'inline', # borrar si no funciona
                filename=f'entrada-{str(ticket.id)[:8]}.pdf',
            )        
            msg.attach(mime_pdf)
        except Exception as e:
            print(f'[EMAIL] Error generando PDF para ticket {ticket.id}: {e}')
    
    try:
        msg.send()
        return f"Email enviado a {order.user.email} (orden {order.id}) con {len(tickets)} PDFs."
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)