import io
import qrcode
from email.mime.image import MIMEImage
from email.mime.application import MIMEApplication
from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone
from .models import Order
from .services import cancel_order
from .ticket_image import generate_ticket_image


@shared_task(name='apps.orders.tasks.expire_pending_orders')
def expire_pending_orders():
    now = timezone.now()
    expired_qs = Order.objects.filter(status='pending', expires_at__lt=now)

    count = 0
    for order in expired_qs.iterator():
        if cancel_order(order, new_status='expired'):
            count += 1

    return f"{count} órdenes expiradas."


@shared_task(name='apps.orders.tasks.send_purchase_confirmation', bind=True, max_retries=3)
def send_purchase_confirmation(self, order_id):
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
    
    # Formateamos las fechas y datos base
    event_date = order.event.start_time.strftime('%d/%m/%Y · %H:%M hs') if order.event.start_time else ''
    venue_name = order.event.venue.name if order.event.venue else ''
    venue_address = order.event.venue.address if order.event.venue else ''
    venue_city = order.event.venue.city if order.event.venue and order.event.venue.city else ''
    buyer_name = order.user.get_full_name() or order.user.username
    paid_at = order.paid_at.strftime('%d/%m/%Y %H:%M') if order.paid_at else ''

    # 1. Armamos la lista de items en Python puro
    items_html = ""
    for item in order.items_snapshot:
        items_html += f"""
        <tr>
            <td style="padding:6px 0;color:#555;">{item['quantity']}x {item['ticket_type_name']}</td>
            <td align="right" style="padding:6px 0;color:#555;">${item['price']}</td>
        </tr>
        """

    # 2. Armamos las tarjetas de los tickets en Python puro
    tickets_html = ""
    for idx, ticket in enumerate(tickets):
        t_name = ticket.ticket_type.name if ticket.ticket_type else 'Entrada'
        tickets_html += f"""
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="border:1px solid #eee;border-radius:8px;margin-bottom:16px;">
            <tr>
                <td style="padding:16px;">
                    <p style="margin:0 0 8px;font-size:14px;font-weight:bold;color:#222;">
                        Ticket {idx + 1} · {t_name}
                    </p>
                    <p style="margin:0 0 12px;font-size:12px;color:#888;">Código: {ticket.id}</p>
                    <img src="cid:qr_{ticket.id}" alt="QR del ticket" width="200" height="200" style="display:block;">
                </td>
            </tr>
        </table>
        """

    # 3. Armamos el HTML completo con f-strings (Cero errores de template)
    html_body = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head><meta charset="UTF-8"><title>Confirmación</title></head>
    <body style="margin:0;padding:0;font-family:Arial,Helvetica,sans-serif;background:#f4f4f4;color:#333;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#f4f4f4;padding:20px 0;">
            <tr>
                <td align="center">
                    <table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" style="background:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
                        <tr>
                            <td style="background:#6a4cf6;color:#ffffff;padding:30px 40px;">
                                <h1 style="margin:0;font-size:24px;">¡Gracias por tu compra!</h1>
                                <p style="margin:8px 0 0;font-size:14px;opacity:0.9;">Tu orden fue confirmada y tus entradas están listas.</p>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding:30px 40px 10px;">
                                <h2 style="margin:0 0 12px;font-size:20px;color:#222;">{order.event.name}</h2>
                                <p style="margin:0 0 4px;font-size:14px;color:#555;">📅 {event_date}</p>
                                <p style="margin:0;font-size:14px;color:#555;">📍 {venue_name} — {venue_address}, {venue_city}</p>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding:20px 40px 0;">
                                <h3 style="margin:0 0 12px;font-size:16px;color:#222;border-bottom:2px solid #eee;padding-bottom:8px;">Resumen de tu orden</h3>
                                <p style="margin:0 0 12px;font-size:13px;color:#888;">Orden #{order.id}<br>Fecha: {paid_at}</p>
                                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="font-size:14px;">
                                    {items_html}
                                    <tr>
                                        <td style="padding:6px 0;color:#888;border-top:1px solid #eee;">Subtotal</td>
                                        <td align="right" style="padding:6px 0;color:#888;border-top:1px solid #eee;">${order.subtotal}</td>
                                    </tr>
                                    <tr>
                                        <td style="padding:6px 0;color:#888;">Cargo por servicio</td>
                                        <td align="right" style="padding:6px 0;color:#888;">${order.platform_fee}</td>
                                    </tr>
                                    <tr>
                                        <td style="padding:12px 0 0;color:#222;font-weight:bold;border-top:2px solid #222;">TOTAL</td>
                                        <td align="right" style="padding:12px 0 0;color:#6a4cf6;font-weight:bold;font-size:18px;border-top:2px solid #222;">${order.total_amount}</td>
                                    </tr>
                                </table>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding:30px 40px 0;">
                                <h3 style="margin:0 0 16px;font-size:16px;color:#222;border-bottom:2px solid #eee;padding-bottom:8px;">Tus entradas</h3>
                                {tickets_html}
                            </td>
                        </tr>
                        <tr>
                            <td style="padding:30px 40px;font-size:12px;color:#999;text-align:center;">
                                <p style="margin:0 0 8px;">Presentá este email o los QRs en el ingreso al evento. Cada QR es de un solo uso.</p>
                                <p style="margin:0;">© Locutronik — Gracias por confiar en nosotros.</p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    text_body = f"Hola {buyer_name},\n\nGracias por tu compra para {order.event.name}.\nRevisá el PDF adjunto con tus entradas.\n\nEl equipo de Locutronik."

    # 4. Creamos y enviamos el mail
    msg = EmailMultiAlternatives(
        subject=f"Tus entradas para {order.event.name}",
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[order.user.email],
    )
    msg.attach_alternative(html_body, 'text/html')

    # 5. Adjuntamos PDFs e Imágenes del QR
    for ticket in tickets:
        try:
            pdf_bytes = generate_ticket_image(ticket)
            mime_pdf = MIMEApplication(pdf_bytes, _subtype='pdf')
            mime_pdf.add_header('Content-Disposition', 'attachment', filename=f'entrada-{str(ticket.id)[:8]}.pdf')
            msg.attach(mime_pdf)

            img_qr = qrcode.make(ticket.qr_code)
            buf = io.BytesIO()
            img_qr.save(buf, format='PNG')
            qr_bytes = buf.getvalue()

            mime_img = MIMEImage(qr_bytes, _subtype='png')
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