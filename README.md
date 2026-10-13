# Locutronik - Backend

API REST para la plataforma de venta de entradas Locutronik.

## Stack

- Django 5.0 + Django REST Framework
- PostgreSQL
- Redis + Celery (tareas asíncronas)
- Mercado Pago (pagos)
- JWT (autenticación)

## Setup local

1. Clonar el repo
2. Crear entorno virtual: `py -3.12 -m venv env`
3. Activar: `env\Scripts\activate` (Windows) o `source env/bin/activate` (Linux/Mac)
4. Instalar dependencias: `pip install -r requirements.txt`
5. Copiar `.env.example` a `.env` y completar valores
6. Correr migraciones: `python manage.py migrate`
7. Crear superusuario: `python manage.py createsuperuser`
8. Levantar: `python manage.py runserver`

## Estructura

- `apps/accounts/` — Usuarios y autenticación
- `apps/events/` — Eventos, venues, tipos de tickets
- `apps/orders/` — Órdenes y tickets
- `apps/payments/` — Integración con Mercado Pago
- `apps/reports/` — Reportes para productores

## Servicios externos

- **Mercado Pago**: pagos
- **SendGrid**: emails transaccionales
- **Redis**: broker de Celery y cache
