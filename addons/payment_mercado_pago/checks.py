"""
System checks — addons.payments

Verifica configuracion critica de seguridad para webhooks.
Cargado desde apps.py al importarse el modulo (register() decorator
corre en tiempo de import).

DEC-BC-01 (2026-05-21): client_secret de MercadoPago obligatorio
en produccion para que `_verify_mp_signature` opere fail-closed
sin perder eventos por rechazo defensivo.

Nota tecnica: usamos django_apps.get_model('payment',
'PaymentGateway') dentro de la funcion en vez de
"from addons.payment.models import PaymentGateway" porque al
cargar este modulo (via apps/payments/apps.py top-level), Django
aun no ha terminado de registrar todos los AppConfigs y el import
de addons.payment.models dispara
django.core.exceptions.AppRegistryNotReady. get_model() es la
forma canonica Django de hacer late-binding al model sin recurrir
a lazy imports (que la regla no-lazy-imports.md prohibe).
"""
from django.apps import apps as django_apps
from django.conf import settings
from django.core.checks import Error, register


@register('payments', deploy=True)
def check_mercadopago_client_secret(app_configs, **kwargs):
    """E001: MercadoPago PaymentGateway must have client_secret in production.

    Razon: `_verify_mp_signature` en webhooks.py retorna `False` cuando no
    encuentra el secret. Sin secret en produccion, todos los webhooks MP se
    rechazan 401 y los pagos quedan sin confirmar via webhook (el polling de
    estado del UC seguiria funcionando pero con latencia).

    **`deploy=True` (H-API-CHK-01):** es un *deployment check* — sólo corre en
    ``manage.py check --deploy`` (el gate de CI/deploy), NO en cada comando
    (``makemigrations``/``migrate``/``runserver``/tests). Antes, registrado
    como check normal con ``DEBUG=False``, bloqueaba ``makemigrations`` en
    cualquier entorno sin un ``PaymentGateway(MERCADOPAGO)`` sembrado — un
    gate de deploy disparándose fuera del deploy. La semántica correcta la
    fija el propio hint ("antes de deploy"). La lógica de validación no
    cambia; el test la invoca directamente, así que sigue verde.
    """
    errors = []
    if settings.DEBUG:
        return errors

    try:
        PGModel = django_apps.get_model('payment', 'PaymentGateway')
        gw = PGModel.objects.filter(gateway='MERCADOPAGO', is_active=True).first()
        if gw is None:
            errors.append(Error(
                'No active PaymentGateway(MERCADOPAGO) found',
                hint='Crear PaymentGateway con gateway=MERCADOPAGO, is_active=True, '
                     'y credentials.client_secret antes de deploy.',
                id='payment.E001',
            ))
            return errors

        creds = gw.get_credentials() or {}
        if not creds.get('client_secret'):
            errors.append(Error(
                'PaymentGateway(MERCADOPAGO) is active but credentials.client_secret is missing',
                hint='Configurar el secret HMAC del webhook MP en gw.credentials.client_secret. '
                     'Sin secret, los webhooks MP se rechazan 401 fail-closed (DEC-BC-01).',
                id='payment.E001',
            ))
    except Exception as exc:
        errors.append(Error(
            f'Cannot verify PaymentGateway(MERCADOPAGO) configuration: {exc!r}',
            hint='Verificar que la tabla settings_payment_gateway existe y es leible.',
            id='payment.E002',
        ))

    return errors
