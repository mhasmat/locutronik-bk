import io
import qrcode
from email.mime.image import MIMEImage
from email.mime.application import MIMEApplication
from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
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
    Envía el email de confirmación con QRs inline y los PDFs adjuntos.
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

    # Pre-procesamos los tickets para pasarle datos simples al template
    tickets_data = []
    for t in tickets:
        tickets_data.append({
            'id': t.id,
            'qr_code': t.qr_code,
            'ticket_type_name': t.ticket_type.name if t.ticket_type else 'Entrada',
        })

    # Armamos un contexto "aplanado" con textos ya formateados
    ctx = {
        'order_id': str(order.id),
        'event_name': order.event.name,
        'event_date': order.event.start_time.strftime('%d/%m/%Y · %H:%M hs') if order.event.start_time else '',
        'venue_name': order.event.venue.name if order.event.venue else '',
        'venue_address': order.event.venue.address if order.event.venue else '',
        'venue_city': order.event.venue.city if order.event.venue and order.event.venue.city else '',
        'buyer_name': order.user.get_full_name() or order.user.username,
        'paid_at_formatted': order.paid_at.strftime('%d/%m/%Y %H:%M') if order.paid_at else '',
        'items_snapshot': order.items_snapshot,
        'subtotal': order.subtotal,
        'platform_fee': order.platform_fee,
        'total_amount': order.total_amount,
        'tickets': tickets_data,
    }
    
    subject = f"Tus entradas para {order.event.name}"
    from django.template.exceptions import TemplateSyntaxError
    try:
        text_body = render_to_string('orders/emails/purchase_confirmation.txt', ctx)
        html_body = render_to_string('orders/emails/purchase_confirmation.html', ctx)
    except TemplateSyntaxError as e:
        print(f"🚨 ERROR DE SINTAXIS EN EL TEMPLATE: {e}")
        return f"Error de sintaxis: {e}"

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[order.user.email],
    )
    msg.attach_alternative(html_body, 'text/html')

    # --- Generar y adjuntar (Inline QR + PDF) ---
    for ticket in tickets:
        try:
            # 1. Generamos la imagen completa en formato PDF
            pdf_bytes = generate_ticket_image(ticket)
            
            # 2. Adjuntamos el PDF
            mime_pdf = MIMEApplication(pdf_bytes, _subtype='pdf')
            mime_pdf.add_header(
                'Content-Disposition', 'attachment',
                filename=f'entrada-{str(ticket.id)[:8]}.pdf',
            )
            msg.attach(mime_pdf)

            # 3. Generamos una versión en PNG solo del QR para embeber en el HTML
            img_qr = qrcode.make(ticket.qr_code)
            buf = io.BytesIO()
            img_qr.save(buf, format='PNG')
            qr_bytes = buf.getvalue()

            mime_img = MIMEImage(qr_bytes, _subtype='png')
            # Este Content-ID coincide con el del template HTML (cid:qr_...)
            mime_img.add_header('Content-ID', f'<qr_{ticket.id}>')
            mime_img.add_header('Content-Disposition', 'inline', filename=f'qr_{ticket.id}.png')
            msg.attach(mime_img)

        except Exception as e:
            print(f"[EMAIL] Error generando archivos para ticket {ticket.id}: {e}")

    try:
        msg.send()
        return f"Email enviado a {order.user.email} (orden {order.id})"
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)