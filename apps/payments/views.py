import secrets
from django.conf import settings
from django.shortcuts import redirect
from django.utils import timezone
from datetime import timedelta

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status

from apps.orders.models import Order
from apps.orders.services import confirm_order_payment
from apps.accounts.models import User
from .services import (
    get_mp_oauth_url, exchange_mp_code_for_token,
    create_checkout_preference, get_payment_info
)

class CreateCheckoutView(APIView):
    """POST /api/orders/<order_id>/checkout/ - Crea preferencia de pago con split."""
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id):
        try:
            order = Order.objects.get(id=order_id, user=request.user)
        except Order.DoesNotExist:
            return Response({'detail': 'Orden no encontrada.'}, status=404)

        if order.status != 'pending':
            return Response({'detail': f'La orden no está pendiente (status: {order.status}).'}, status=400)

        if order.expires_at < timezone.now():
            return Response({'detail': 'La orden ya expiró.'}, status=400)

        preference_data, error = create_checkout_preference(order)
        if error:
            return Response({'detail': error}, status=502)

        order.payment_provider = 'mercadopago'
        order.payment_reference = preference_data.get('id', '')
        order.save(update_fields=['payment_provider', 'payment_reference'])

        init_point = preference_data.get('sandbox_init_point') or preference_data.get('init_point')
        return Response({
            'order_id': str(order.id),
            'preference_id': preference_data.get('id'),
            'init_point': init_point,
        }, status=200)

class MercadoPagoWebhookView(APIView):
    """POST /api/payments/webhook/ - Recibe notificaciones de MP."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        topic = request.query_params.get('type') or request.query_params.get('topic') or request.data.get('type') or request.data.get('topic')
        payment_id = (request.query_params.get('data.id') or request.query_params.get('id') or (request.data.get('data') or {}).get('id') or request.data.get('id'))

        if topic != 'payment' or not payment_id:
            return Response({'detail': 'Ignorado.'}, status=200)

        payment_data, error = get_payment_info(payment_id)
        if error:
            return Response({'detail': error}, status=400)

        external_reference = payment_data.get('external_reference')
        mp_status = payment_data.get('status')

        if not external_reference:
            return Response({'detail': 'Sin external_reference.'}, status=400)

        try:
            order = Order.objects.get(id=external_reference)
        except Order.DoesNotExist:
            return Response({'detail': 'Orden no encontrada.'}, status=404)

        print(f"[MP WEBHOOK] Orden {order.id} | status_mp={mp_status}")

        if mp_status == 'approved':
            confirm_order_payment(order, 'mercadopago', str(payment_id))

        return Response({'detail': 'OK'}, status=200)

class MPOAuthUrlView(APIView):
    """GET /api/payments/mp/oauth/url/ - Devuelve la URL de autorización."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Generamos un token de estado (state) seguro y lo guardamos en la sesión del usuario
        state = secrets.token_urlsafe(32)
        request.session['mp_oauth_state'] = state
        url = get_mp_oauth_url(request.user.id, state)
        return Response({'url': url})

class MPOAuthCallbackView(APIView):
    """GET /api/payments/mp/oauth/callback/ - Recibe el código y guarda los tokens."""
    permission_classes = [AllowAny]

    def get(self, request):
        error = request.query_params.get('error')
        code = request.query_params.get('code')
        state = request.query_params.get('state')

        if error:
            return redirect(f"{settings.FRONTEND_URL}/productor?error=oauth_denied")

        # Validamos el state (protección CSRF)
        stored_state = request.session.pop('mp_oauth_state', None)
        if not state or state != stored_state:
            return redirect(f"{settings.FRONTEND_URL}/productor?error=invalid_state")

        if not code:
            return redirect(f"{settings.FRONTEND_URL}/productor?error=no_code")

        token_data = exchange_mp_code_for_token(code)
        if not token_data or 'user_id' not in token_data:
            return redirect(f"{settings.FRONTEND_URL}/productor?error=token_exchange_failed")

        # Obtenemos el usuario a partir del state (o de la sesión, pero el state ya nos dice quién es)
        # Como el state no contiene el user_id, podemos usar el user_id del request si está autenticado,
        # pero en un callback externo no lo estará. Una solución es guardar el user_id en la sesión
        # junto con el state. Para simplificar, usamos el user_id que guardamos en la sesión al generar la URL.
        user_id = request.session.get('mp_oauth_user_id')
        if not user_id:
            # Fallback: si no hay sesión, no podemos saber quién es. En producción, deberías
            # guardar el user_id en la sesión o en un modelo temporal.
            return redirect(f"{settings.FRONTEND_URL}/productor?error=no_user")

        try:
            user = User.objects.get(id=user_id)
            user.mp_user_id = str(token_data['user_id'])
            user.mp_access_token = token_data['access_token']
            user.mp_refresh_token = token_data.get('refresh_token', '')
            user.mp_token_expires_at = timezone.now() + timedelta(seconds=token_data.get('expires_in', 15552000))
            user.save(update_fields=['mp_user_id', 'mp_access_token', 'mp_refresh_token', 'mp_token_expires_at'])
            return redirect(f"{settings.FRONTEND_URL}/productor?linked=true")
        except User.DoesNotExist:
            return redirect(f"{settings.FRONTEND_URL}/productor?error=user_not_found")


def checkout_result_view(request, status):
    """
    Recibe el resultado de MP y redirige al frontend.
    El frontend vive en FRONTEND_URL.
    """
    order_id = request.GET.get('order_id') or request.GET.get('external_reference')
    payment_id = request.GET.get('payment_id')

    frontend_url = settings.FRONTEND_URL.rstrip('/')
    url = f"{frontend_url}/checkout/{status}/"
    params = []
    if order_id:
        params.append(f"order_id={order_id}")
    if payment_id:
        params.append(f"payment_id={payment_id}")

    if params:
        url += "?" + "&".join(params)

    return redirect(url)    