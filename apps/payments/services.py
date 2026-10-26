import mercadopago
import urllib.parse
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


def get_mp_oauth_url(user_id):
    """Genera la URL de autorización de Mercado Pago."""
    # Usamos el APP_ID de Mercado Pago (lo vas a tener en el .env)
    app_id = settings.MP_CLIENT_ID
    # La URL a la que MP nos devolverá el código de autorización
    redirect_uri = f"{settings.BACKEND_URL}/api/payments/mp/oauth/callback/"
    
    # Pasamos el user_id en el 'state' para saber quién se está vinculando
    params = {
        'client_id': app_id,
        'response_type': 'code',
        'platform_id': 'mp',
        'redirect_uri': redirect_uri,
        'state': str(user_id)
    }
    
    url = f"https://auth.mercadopago.com.ar/authorization?{urllib.parse.urlencode(params)}"
    return url


def exchange_mp_code_for_token(code):
    """Intercambia el código de autorización por el access_token y el user_id del vendedor."""
    import requests
    
    url = "https://api.mercadopago.com/oauth/token"
    payload = {
        "client_id": settings.MP_CLIENT_ID,
        "client_secret": settings.MP_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": f"{settings.BACKEND_URL}/api/payments/mp/oauth/callback/"
    }
    
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        return response.json() # Contiene access_token, user_id, etc.
    return None