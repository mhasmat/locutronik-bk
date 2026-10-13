import io
import qrcode

from email.mime.image import MIMEImage

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.db.models import F

from .models import Order, TicketType
from .services import cancel_order


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
    Envía el email de confirmación de compra con los QRs embebidos y adjuntos.
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

    # --- Adjuntar QRs como imágenes inline (CID) + adjuntos ---
    for ticket in tickets:
        img = qrcode.make(ticket.qr_code)
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        img_bytes = buf.getvalue()

        # Inline (referenciada desde el HTML con cid:qr_<ticket.id>)
        mime_img = MIMEImage(img_bytes, _subtype='png')
        mime_img.add_header('Content-ID', f'<qr_{ticket.id}>')
        mime_img.add_header(
            'Content-Disposition', 'inline',
            filename=f'qr_{ticket.id}.png',
        )
        msg.attach(mime_img)

        # Adjunto descargable
        mime_img_attach = MIMEImage(img_bytes, _subtype='png')
        mime_img_attach.add_header(
            'Content-Disposition', 'attachment',
            filename=f'ticket_{ticket.id}.png',
        )
        msg.attach(mime_img_attach)

    try:
        msg.send()
        return f"Email enviado a {order.user.email} (orden {order.id})."
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)