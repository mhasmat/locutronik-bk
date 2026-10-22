import io
from django.utils import timezone
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.units import cm
from django.conf import settings

def generate_settlement_pdf(settlement):
    """Genera un comprobante de rendición en PDF."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm
    )
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Estilos personalizados
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        textColor=colors.HexColor('#6a4cf6'),
        alignment=1, # Centrado
        spaceAfter=20
    )
    normal_style = styles['Normal']
    bold_style = ParagraphStyle('BoldStyle', parent=normal_style, fontName='Helvetica-Bold')
    
    # --- Encabezado ---
    elements.append(Paragraph("COMPROBANTE DE RENDICIÓN", title_style))
    
    # --- Datos Generales ---
    producer_name = settlement.producer.get_full_name() or settlement.producer.username
    date_str = settlement.created_at.strftime('%d/%m/%Y %H:%M')
    type_str = "PARCIAL" if settlement.settlement_type == 'partial' else "FINAL"
    
    data_general = [
        [Paragraph("<b>Locutronik</b>", normal_style), Paragraph(f"<b>Comprobante N°:</b> {settlement.id}", normal_style)],
        [Paragraph(f"<b>Productor:</b> {producer_name} (@{settlement.producer.username})", normal_style), Paragraph(f"<b>Fecha:</b> {date_str}", normal_style)],
        [Paragraph(f"<b>Tipo:</b> Rendición {type_str}", normal_style), Paragraph(f"<b>Emitido por:</b> {settlement.created_by.username}", normal_style)],
    ]
    table_general = Table(data_general, colWidths=[9*cm, 8*cm])
    table_general.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f9fafb')),
        ('PADDING', (0,0), (-1,-1), 10),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#e5e7eb')),
    ]))
    elements.append(table_general)
    elements.append(Spacer(1, 20))
    
    # --- Detalle de Ventas ---
    elements.append(Paragraph("<b>Detalle de Entradas Incluidas</b>", styles['Heading2']))
    elements.append(Spacer(1, 10))
    
    table_data = [["Fecha", "Evento", "Método", "Subtotal"]]
    
    for order in settlement.orders.all():
        table_data.append([
            order.paid_at.strftime('%d/%m/%Y'),
            order.event.name[:30] + ("..." if len(order.event.name) > 30 else ""),
            order.get_payment_method_display().upper() if hasattr(order, 'get_payment_method_display') else order.payment_method.upper(),
            f"${order.subtotal:,.2f}"
        ])
        
    table_orders = Table(table_data, colWidths=[3*cm, 8*cm, 3*cm, 3*cm])
    table_orders.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#6a4cf6')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('ALIGN', (3,0), (3,-1), 'RIGHT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('BACKGROUND', (0,1), (-1,-1), colors.white),
        ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#e5e7eb')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f9fafb')])
    ]))
    elements.append(table_orders)
    elements.append(Spacer(1, 30))
    
    # --- Resumen Económico ---
    elements.append(Paragraph("<b>Resumen de Liquidación</b>", styles['Heading2']))
    elements.append(Spacer(1, 10))
    
    data_totales = [
        ["Concepto", "Monto"],
        ["Total Recaudado (Bruto)", f"${settlement.total_gross:,.2f}"],
        ["Fee Locutronik", f"-${settlement.total_fee:,.2f}"],
        ["Desglose en Efectivo", f"${settlement.cash_amount:,.2f}"],
        ["Desglose en Transferencia", f"${settlement.transfer_amount:,.2f}"],
        ["TOTAL NETO A PAGAR AL PRODUCTOR", f"${settlement.total_net:,.2f}"],
    ]
    
    table_totales = Table(data_totales, colWidths=[12*cm, 5*cm])
    table_totales.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'RIGHT'),
        ('ALIGN', (0,0), (0,-1), 'LEFT'),
        ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0,-1), (-1,-1), colors.HexColor('#6a4cf6')),
        ('FONTSIZE', (0,-1), (-1,-1), 12),
        ('LINEABOVE', (0,-1), (-1,-1), 2, colors.HexColor('#6a4cf6')),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ]))
    elements.append(table_totales)
    
    # Pie de página
    elements.append(Spacer(1, 50))
    elements.append(Paragraph("Este documento es un comprobante válido de la rendición de entradas vendidas a través de Locutronik. Conserve este recibo para sus registros contables.", ParagraphStyle('Footer', parent=normal_style, fontSize=9, textColor=colors.gray, alignment=1)))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()