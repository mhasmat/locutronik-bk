import mercadopago
import requests
import urllib.parse
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

def get_mp_sdk():
    """Devuelve una instancia configurada del SDK de Mercado Pago (cuenta de la plataforma)."""
    return mercadopago.SDK(settings.MP_ACCESS_TOKEN)

def get_mp_oauth_url(user_id, state_token):
    """Genera la URL de autorización de Mercado Pago para que el productor vincule su cuenta."""
    params = {
        'client_id': settings.MP_CLIENT_ID,
        'response_type': 'code',
        'platform_id': 'mp',
        'redirect_uri': f"{settings.BACKEND_URL.rstrip('/')}/api/payments/mp/oauth/callback/",
        'state': state_token
    }
    return f"https://auth.mercadopago.com.ar/authorization?{urllib.parse.urlencode(params)}"

def exchange_mp_code_for_token(code):
    """Intercambia el código de autorización por los tokens del vendedor."""
    url = "https://api.mercadopago.com/oauth/token"
    payload = {
        "client_id": settings.MP_CLIENT_ID,
        "client_secret": settings.MP_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": f"{settings.BACKEND_URL.rstrip('/')}/api/payments/mp/oauth/callback/"
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post(url, data=payload, headers=headers)
    if response.status_code == 200:
        return response.json()
    return None

def create_checkout_preference(order):
    """
    Crea una preferencia de pago en Mercado Pago con split payment.
    La comisión de Locutronik se retiene automáticamente.
    """
    sdk = get_mp_sdk()
    event = order.event
    producer = event.organizer

    if not producer.mp_access_token:
        return None, "El productor no ha vinculado su cuenta de Mercado Pago."

    # Preparamos los items (precio + fee para el cliente)
    mp_items = []
    for item in order.items_snapshot:
        mp_items.append({
            'title': f"{event.name} - {item['ticket_type_name']}",
            'quantity': item['quantity'],
            'unit_price': float(item['price']) + float(item['fee']),
            'currency_id': 'ARS',
        })

    # URLs de retorno
    success_url = f"{settings.FRONTEND_URL.rstrip('/')}/checkout/success?order_id={order.id}"
    failure_url = f"{settings.FRONTEND_URL.rstrip('/')}/checkout/failure?order_id={order.id}"
    pending_url = f"{settings.FRONTEND_URL.rstrip('/')}/checkout/pending?order_id={order.id}"
    webhook_url = f"{settings.BACKEND_URL.rstrip('/')}/api/payments/webhook/"

    # 👇 CÁLCULO DEL FEE PARA EL SPLIT
    # El marketplace_fee es la comisión que se queda Locutronik (en la cuenta de la plataforma).
    # El resto se transfiere automáticamente a la cuenta del productor.
    marketplace_fee = float(order.platform_fee)

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
        "marketplace_fee": marketplace_fee, # 👈 Comisión para Locutronik
        "statement_descriptor": "LOCUTRONIK",
        "expires": True,
        "expiration_date_from": order.created_at.isoformat(),
        "expiration_date_to": order.expires_at.isoformat(),
    }

    try:
        # Usamos el access_token del productor para que la transacción se realice en su nombre
        result = sdk.preference().create(preference_data, access_token=producer.mp_access_token)
    except Exception as e:
        return None, f"Error al contactar Mercado Pago: {e}"

    if result.get('status') not in (200, 201):
        return None, f"Mercado Pago devolvió error: {result}"

    return result['response'], None

def get_payment_info(payment_id):
    """Consulta un pago por ID (usando el token de la plataforma)."""
    sdk = get_mp_sdk()
    try:
        result = sdk.payment().get(payment_id)
    except Exception as e:
        return None, f"Error al consultar el pago: {e}"
    if result.get('status') != 200:
        return None, f"MP devolvió estado {result.get('status')}"
    return result['response'], None