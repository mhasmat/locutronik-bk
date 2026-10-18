import io
from PIL import Image, ImageDraw, ImageFont
import qrcode
from pathlib import Path

# Colores de la marca
BRAND_DARK = (30, 27, 45)
BRAND_WHITE = (255, 255, 255)
BRAND_GRAY = (180, 180, 200)

# Tamaño de la imagen (formato vertical, ideal para WhatsApp e impresión)
WIDTH, HEIGHT = 1080, 1350


def _get_font(size, bold=False):
    candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for path in candidates:
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size)
            except Exception:
                continue
    return ImageFont.load_default()


def _text_size(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _draw_centered_text(draw, text, y, font, fill, max_width=None):
    if max_width:
        w, _ = _text_size(draw, text, font)
        while w > max_width and len(text) > 3:
            text = text[:-4] + "..."
            w, _ = _text_size(draw, text, font)

    w, h = _text_size(draw, text, font)
    x = (WIDTH - w) // 2
    draw.text((x, y), text, font=font, fill=fill)
    return h


def _draw_left_text(draw, text, x, y, font, fill, max_width=None):
    if max_width:
        w, _ = _text_size(draw, text, font)
        while w > max_width and len(text) > 3:
            text = text[:-4] + "..."
            w, _ = _text_size(draw, text, font)

    draw.text((x, y), text, font=font, fill=fill)


def _get_event_color(event):
    palette = [
        (106, 76, 246),   # violeta
        (233, 69, 96),    # rojo
        (26, 158, 143),   # teal
        (240, 130, 50),   # naranja
        (74, 123, 200),   # azul
        (200, 79, 176),   # magenta
    ]
    return palette[event.id % len(palette)]


def generate_ticket_image(ticket):
    """Genera una imagen vertical de la entrada lista para compartir o imprimir."""
    order = ticket.order
    event = order.event
    venue = event.venue
    user = order.user

    # --- Lienzo base ---
    img = Image.new('RGB', (WIDTH, HEIGHT), BRAND_DARK)
    draw = ImageDraw.Draw(img)

    # --- Header con gradiente del color del evento ---
    header_height = 320
    accent = _get_event_color(event)

    for y in range(header_height):
        ratio = y / header_height
        r = int(accent[0] * (1 - ratio * 0.6))
        g = int(accent[1] * (1 - ratio * 0.6))
        b = int(accent[2] * (1 - ratio * 0.6))
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))

    # Imagen del evento (usando .open para Supabase)
    if event.image:
        try:
            event_img_file = event.image.open('rb')
            event_img = Image.open(event_img_file).convert('RGB')

            # Crop para llenar el header
            ratio_w = WIDTH / event_img.width
            ratio_h = header_height / event_img.height
            ratio = max(ratio_w, ratio_h)
            new_size = (int(event_img.width * ratio), int(event_img.height * ratio))
            event_img = event_img.resize(new_size, Image.LANCZOS)

            left = (event_img.width - WIDTH) // 2
            top = (event_img.height - header_height) // 2
            event_img = event_img.crop((left, top, left + WIDTH, top + header_height))

            # Oscurecer para legibilidad
            overlay = Image.new('RGB', (WIDTH, header_height), (0, 0, 0))
            event_img = Image.blend(event_img, overlay, 0.45)

            img.paste(event_img, (0, 0))
        except Exception as e:
            print(f"Error al procesar imagen del evento: {e}")

    # --- Título y subtítulo ---
    font_title = _get_font(60, bold=True)
    font_subtitle = _get_font(28)
    font_label = _get_font(24)
    font_value = _get_font(32, bold=True)
    font_small = _get_font(20)

    _draw_centered_text(draw, event.name, 100, font_title, BRAND_WHITE, max_width=WIDTH - 80)
    _draw_centered_text(draw, f"🎫  {ticket.ticket_type.name}", 200, font_subtitle, BRAND_WHITE)

    # --- Sección de datos ---
    y = header_height + 50

    date_str = event.start_time.strftime('%d/%m/%Y · %H:%M hs')
    _draw_left_text(draw, 'FECHA Y HORA', 60, y, font_label, BRAND_GRAY)
    _draw_left_text(draw, date_str, 60, y + 35, font_value, BRAND_WHITE)
    y += 120

    _draw_left_text(draw, 'LUGAR', 60, y, font_label, BRAND_GRAY)
    _draw_left_text(draw, venue.name, 60, y + 35, font_value, BRAND_WHITE)
    if venue.address:
        _draw_left_text(draw, f"{venue.address}, {venue.city}", 60, y + 75, font_small, BRAND_GRAY)
    y += 140

    # --- QR ---
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=2,
    )
    qr.add_data(ticket.qr_code)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')

    qr_size = 460
    qr_img = qr_img.resize((qr_size, qr_size), Image.LANCZOS)
    qr_bg_size = qr_size + 40
    qr_bg = Image.new('RGB', (qr_bg_size, qr_bg_size), BRAND_WHITE)
    qr_bg.paste(qr_img, (20, 20))

    qr_x = (WIDTH - qr_bg_size) // 2
    img.paste(qr_bg, (qr_x, y))
    y += qr_bg_size + 30

    # --- Código y comprador ---
    ticket_code = str(ticket.id)[:8].upper()
    _draw_centered_text(draw, f"Código: {ticket_code}", y, font_small, BRAND_GRAY, max_width=WIDTH - 100)
    y += 40
    
    buyer = user.get_full_name() or user.username
    _draw_centered_text(draw, f"A nombre de: {buyer}", y, font_small, BRAND_WHITE)

    # --- Footer ---
    footer_y = HEIGHT - 140
    draw.rectangle([(0, footer_y), (WIDTH, HEIGHT)], fill=(0, 0, 0))

    instructions = [
        '⚠️  Llegá 30 minutos antes al evento',
        '🔒  No compartas este código con nadie',
        '📱  Mostrá el QR desde tu celular en el ingreso',
    ]
    for i, line in enumerate(instructions):
        _draw_centered_text(draw, line, footer_y + 20 + i * 32, font_small, BRAND_GRAY, max_width=WIDTH - 60)

    draw.rectangle([(0, HEIGHT - 25), (WIDTH, HEIGHT)], fill=accent)
    _draw_centered_text(draw, 'Locutronik', HEIGHT - 22, font_small, BRAND_WHITE)

    # --- Exportar ---
    buf = io.BytesIO()
    img.save(buf, format='PDF', optimize=True, resolution=100.0)
    return buf.getvalue()