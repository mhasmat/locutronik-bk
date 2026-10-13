import mercadopago
from django.conf import settings

def get_mp_sdk():
    """Devuelve una instancia configurada del SDK de Mercado Pago."""
    return mercadopago.SDK(settings.MP_ACCESS_TOKEN)


def create_checkout_preference(order):
    sdk = get_mp_sdk()

    mp_items = []
    for item in order.items_snapshot:
        mp_items.append({
            'title': f"{order.event.name} - {item['ticket_type_name']}",
            'quantity': item['quantity'],
            'unit_price': float(item['price']) + float(item['fee']),
            'currency_id': 'ARS',
        })

    # 👇 CAMBIO: usar BACKEND_URL (ngrok) en vez de FRONTEND_URL
    base = settings.BACKEND_URL.rstrip('/')
    skip = 'ngrok-skip-browser-warning=true'

    success_url = f"{base}/api/payments/checkout/success/?order_id={order.id}&{skip}"
    failure_url = f"{base}/api/payments/checkout/failure/?order_id={order.id}&{skip}"
    pending_url = f"{base}/api/payments/checkout/pending/?order_id={order.id}&{skip}"

    webhook_url = f"{base}/api/payments/webhook/"

    preference_data = {
        "items": mp_items,
        "external_reference": str(order.id),
        "back_urls": {
            "success": success_url,
            "failure": failure_url,
            "pending": pending_url,
        },
        "auto_return": "approved",
        "notification_url": webhook_url,
        "statement_descriptor": "LOCUTRONIK",
        "expires": True,
        "expiration_date_from": order.created_at.isoformat(),
        "expiration_date_to": order.expires_at.isoformat(),
    }

    try:
        result = sdk.preference().create(preference_data)
    except Exception as e:
        return None, f"Error al contactar Mercado Pago: {e}"

    if result.get('status') not in (200, 201):
        return None, f"Mercado Pago devolvió error: {result}"

    return result['response'], None


def get_payment_info(payment_id):
    """
    Consulta un pago por ID. Devuelve (payment_data, error_message).
    """
    sdk = get_mp_sdk()
    try:
        result = sdk.payment().get(payment_id)
    except Exception as e:
        return None, f"Error al consultar el pago: {e}"

    if result.get('status') != 200:
        return None, f"MP devolvió estado {result.get('status')}"

    return result['response'], None