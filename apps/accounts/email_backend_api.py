import logging
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.message import sanitize_address

logger = logging.getLogger(__name__)


class SendGridAPIBackend(BaseEmailBackend):
    """
    Backend de email que usa la API HTTP de SendGrid (puerto 443)
    en lugar de SMTP (puerto 587). Más confiable en hosting como Render.
    """

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import (
                Mail, Attachment, FileContent, FileName, FileType,
                Disposition, ContentId
            )
        except ImportError:
            logger.error("sendgrid no está instalado")
            raise

        api_key = settings.SENDGRID_API_KEY
        if not api_key:
            logger.error("SENDGRID_API_KEY no está configurada")
            return 0

        sg = SendGridAPIClient(api_key)
        num_sent = 0

        for message in email_messages:
            try:
                from_email = sanitize_address(message.from_email, 'utf-8')
                to_emails = [
                    sanitize_address(addr, message.encoding)
                    for addr in message.to
                ]

                mail = Mail(
                    from_email=from_email,
                    to_emails=to_emails,
                    subject=message.subject,
                )

                # Cuerpo: HTML si existe, sino texto plano
                html_content = None
                for content, mimetype in getattr(message, 'alternatives', []):
                    if mimetype == 'text/html':
                        html_content = content
                        break

                if html_content:
                    mail.add_content(html_content, 'text/html')
                if message.body:
                    mail.add_content(message.body, 'text/plain')

                # Adjuntos — preservando Content-ID para imágenes inline
                for attachment in message.attachments:
                    if isinstance(attachment, tuple):
                        # Formato (filename, content, mimetype)
                        filename, content, mimetype = attachment
                        content_id = None
                        disposition = 'attachment'
                    else:
                        # Objeto MIMEBase (MIMEImage, MIMEApplication, etc.)
                        filename = attachment.get_filename() or 'file'
                        content = attachment.get_payload(decode=True)
                        mimetype = attachment.get_content_type()

                        # Leemos el Content-ID si existe (imágenes inline)
                        raw_cid = attachment.get('Content-ID', '')
                        content_id = raw_cid.strip('<>').strip() if raw_cid else None

                        # Si tiene Content-ID, es inline; sino, es adjunto normal
                        disposition = 'inline' if content_id else 'attachment'

                    att = Attachment(
                        FileContent(content),
                        FileName(filename),
                        FileType(mimetype or 'application/octet-stream'),
                        Disposition(disposition),
                    )

                    if content_id:
                        att.content_id = ContentId(content_id)

                    mail.add_attachment(att)

                response = sg.send(mail)

                if response.status_code in (200, 201, 202):
                    num_sent += 1
                else:
                    logger.warning(
                        f"SendGrid respondió {response.status_code}: {response.body}"
                    )

            except Exception as e:
                logger.exception(f"Error enviando email: {e}")
                if not self.fail_silently:
                    raise

        return num_sent