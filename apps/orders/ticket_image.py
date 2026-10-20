import io
import qrcode
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

# Colores para el ticket A4/Digital
BRAND_DARK = (30, 27, 45)
BRAND_WHITE = (255, 255, 255)
BRAND_GRAY = (180, 180, 200)

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
    x = (1080 - w) // 2 if y < 1350 else (576 - w) // 2 # Ajuste según ancho
    draw.text((x, y), text, font=font, fill=fill)
    return h

def _get_event_color(event):
    palette = [
        (106, 76, 246), (233, 69, 96), (26, 158, 143),
        (240, 130, 50), (74, 123, 200), (200, 79, 176),
    ]
    return palette[event.id % len(palette)]


# ==========================================
# 1. TICKET DIGITAL (Formato Vertical grande)
# ==========================================
def generate_ticket_image(ticket):
    """Genera una imagen vertical de la entrada lista para compartir o imprimir."""
    order = ticket.order
    event = order.event
    venue = event.venue
    user = order.user

    WIDTH, HEIGHT = 1080, 1350
    img = Image.new('RGB', (WIDTH, HEIGHT), BRAND_DARK)
    draw = ImageDraw.Draw(img)

    header_height = 320
    accent = _get_event_color(event)

    for y in range(header_height):
        ratio = y / header_height
        r = int(accent[0] * (1 - ratio * 0.6))
        g = int(accent[1] * (1 - ratio * 0.6))
        b = int(accent[2] * (1 - ratio * 0.6))
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))

    if event.image:
        try:
            event_img_file = event.image.open('rb')
            event_img = Image.open(event_img_file).convert('RGB')
            ratio_w = WIDTH / event_img.width
            ratio_h = header_height / event_img.height
            ratio = max(ratio_w, ratio_h)
            new_size = (int(event_img.width * ratio), int(event_img.height * ratio))
            event_img = event_img.resize(new_size, Image.LANCZOS)
            left = (event_img.width - WIDTH) // 2
            top = (event_img.height - header_height) // 2
            event_img = event_img.crop((left, top, left + WIDTH, top + header_height))
            overlay = Image.new('RGB', (WIDTH, header_height), (0, 0, 0))
            event_img = Image.blend(event_img, overlay, 0.45)
            img.paste(event_img, (0, 0))
        except Exception as e:
            print(f"Error al procesar imagen del evento: {e}")

    font_title = _get_font(60, bold=True)
    font_subtitle = _get_font(28)
    font_label = _get_font(24)
    font_value = _get_font(32, bold=True)
    font_small = _get_font(20)

    # Centrar textos ajustando el ancho a 1080
    w, _ = _text_size(draw, event.name, font_title)
    draw.text(((WIDTH - w)//2, 100), event.name, font=font_title, fill=BRAND_WHITE)

    t_name = ticket.ticket_type.name if ticket.ticket_type else 'Entrada'
    w, _ = _text_size(draw, f"🎫  {t_name}", font_subtitle)
    draw.text(((WIDTH - w)//2, 200), f"🎫  {t_name}", font=font_subtitle, fill=BRAND_WHITE)

    y = header_height + 40
    date_str = event.start_time.strftime('%d/%m/%Y · %H:%M hs')
    draw.text((60, y), 'FECHA Y HORA', font=font_label, fill=BRAND_GRAY)
    draw.text((60, y + 35), date_str, font=font_value, fill=BRAND_WHITE)
    y += 100

    draw.text((60, y), 'LUGAR', font=font_label, fill=BRAND_GRAY)
    draw.text((60, y + 35), venue.name, font=font_value, fill=BRAND_WHITE)
    if venue.address:
        draw.text((60, y + 75), f"{venue.address}, {venue.city}", font=font_small, fill=BRAND_GRAY)
    y += 120

    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(ticket.qr_code)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    qr_img = qr_img.resize((380, 380), Image.LANCZOS)
    qr_bg = Image.new('RGB', (420, 420), BRAND_WHITE)
    qr_bg.paste(qr_img, (20, 20))
    img.paste(qr_bg, ((WIDTH - 420) // 2, y))
    y += 450

    ticket_code = str(ticket.id)[:8].upper()
    w, _ = _text_size(draw, f"Código: {ticket_code}", font_small)
    draw.text(((WIDTH - w)//2, y), f"Código: {ticket_code}", font=font_small, fill=BRAND_GRAY)
    y += 40

    buyer = user.get_full_name() or user.username
    w, _ = _text_size(draw, f"A nombre de: {buyer}", font_small)
    draw.text(((WIDTH - w)//2, y), f"A nombre de: {buyer}", font=font_small, fill=BRAND_WHITE)

    footer_y = HEIGHT - 140
    draw.rectangle([(0, footer_y), (WIDTH, HEIGHT)], fill=(0, 0, 0))
    instructions = [
        '⚠️  Llegá 30 minutos antes al evento',
        '🔒  No compartas este código con nadie',
        '📱  Mostrá el QR desde tu celular en el ingreso',
    ]
    for i, line in enumerate(instructions):
        w, _ = _text_size(draw, line, font_small)
        draw.text(((WIDTH - w)//2, footer_y + 20 + i * 32), line, font=font_small, fill=BRAND_GRAY)

    draw.rectangle([(0, HEIGHT - 25), (WIDTH, HEIGHT)], fill=accent)
    w, _ = _text_size(draw, 'Locutronik', font_small)
    draw.text(((WIDTH - w)//2, HEIGHT - 22), 'Locutronik', font=font_small, fill=BRAND_WHITE)

    buf = io.BytesIO()
    img.save(buf, format='PDF', resolution=100.0)
    return buf.getvalue()


# ==========================================
# 2. TICKET TÉRMICO (Formato Tira 80mm)
# ==========================================
def generate_thermal_ticket(ticket):
    """Genera un ticket de formato vertical (80mm) para impresora térmica."""
    order = ticket.order
    event = order.event
    venue = event.venue
    user = order.user

    W = 576
    H = 1100
    img = Image.new('RGB', (W, H), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    font_title = _get_font(36, bold=True)
    font_sub = _get_font(24)
    font_normal = _get_font(22)
    font_small = _get_font(18)
    
    y = 30
    
    # 1. Encabezado
    w, _ = _text_size(draw, "TICKET DE ENTRADA", font_sub)
    draw.text(((W - w)//2, y), "TICKET DE ENTRADA", font=font_sub, fill=(0,0,0))
    y += 40
    
    w, _ = _text_size(draw, event.name.upper(), font_title)
    if w > W - 40: # Truncar si es muy largo
        event_name = event.name.upper()[:20] + "..."
        w, _ = _text_size(draw, event_name, font_title)
        draw.text(((W - w)//2, y), event_name, font=font_title, fill=(0,0,0))
    else:
        draw.text(((W - w)//2, y), event.name.upper(), font=font_title, fill=(0,0,0))
    y += 50
    
    # Separador
    draw.line([(20, y), (W-20, y)], fill=(0,0,0), width=2)
    y += 20
    
    # 2. Datos
    date_str = f"FECHA: {event.start_time.strftime('%d/%m/%Y %H:%M hs')}"
    w, _ = _text_size(draw, date_str, font_normal)
    draw.text(((W - w)//2, y), date_str, font=font_normal, fill=(0,0,0))
    y += 35
    
    place_str = f"LUGAR: {venue.name}"
    w, _ = _text_size(draw, place_str, font_normal)
    if w > W - 40:
        place_str = f"LUGAR: {venue.name[:25]}..."
        w, _ = _text_size(draw, place_str, font_normal)
    draw.text(((W - w)//2, y), place_str, font=font_normal, fill=(0,0,0))
    y += 35
    
    if venue.address:
        addr_str = f"{venue.address}, {venue.city}"
        w, _ = _text_size(draw, addr_str, font_small)
        if w > W - 40:
            addr_str = f"{venue.address[:30]}..."
            w, _ = _text_size(draw, addr_str, font_small)
        draw.text(((W - w)//2, y), addr_str, font=font_small, fill=(0,0,0))
    y += 40
    
    draw.line([(20, y), (W-20, y)], fill=(0,0,0), width=2)
    y += 20
    
    # 3. Info del Ticket
    t_name = ticket.ticket_type.name if ticket.ticket_type else 'Entrada'
    type_str = f"TIPO: {t_name.upper()}"
    w, _ = _text_size(draw, type_str, font_sub)
    draw.text(((W - w)//2, y), type_str, font=font_sub, fill=(0,0,0))
    y += 40
    
    buyer = user.get_full_name() or user.username
    buyer_str = f"COMPRADOR: {buyer.upper()}"
    w, _ = _text_size(draw, buyer_str, font_small)
    if w > W - 40:
        buyer_str = f"COMPRADOR: {buyer[:25].upper()}..."
        w, _ = _text_size(draw, buyer_str, font_small)
    draw.text(((W - w)//2, y), buyer_str, font=font_small, fill=(0,0,0))
    y += 35
    
    order_str = f"ORDEN: #{str(order.id)[:8].upper()}"
    w, _ = _text_size(draw, order_str, font_small)
    draw.text(((W - w)//2, y), order_str, font=font_small, fill=(0,0,0))
    y += 50
    
    # 4. QR (grande)
    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(ticket.qr_code)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    qr_img = qr_img.resize((300, 300), Image.LANCZOS)
    img.paste(qr_img, ((W - 300) // 2, y))
    y += 320
    
    # 5. Pie
    code_str = f"COD: {str(ticket.id)[:8].upper()}"
    w, _ = _text_size(draw, code_str, font_normal)
    draw.text(((W - w)//2, y), code_str, font=font_normal, fill=(0,0,0))
    y += 40
    
    draw.line([(20, y), (W-20, y)], fill=(0,0,0), width=2)
    y += 20
    
    footer1 = "Presenta este ticket en la puerta."
    w, _ = _text_size(draw, footer1, font_small)
    draw.text(((W - w)//2, y), footer1, font=font_small, fill=(0,0,0))
    y += 25
    
    footer2 = "Locutronik.com"
    w, _ = _text_size(draw, footer2, font_small)
    draw.text(((W - w)//2, y), footer2, font=font_small, fill=(0,0,0))
    
    # Recortar la altura final
    img = img.crop((0, 0, W, y + 40))
    
    buf = io.BytesIO()
    img.save(buf, format='PDF', resolution=100.0)
    return buf.getvalue()