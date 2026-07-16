"""
setup_mp_gateway — crea o actualiza el PaymentGateway de MercadoPago.

Lee las credenciales desde variables de entorno (con fallback a
decouple/.env) y guarda el registro PaymentGateway cifrado en la DB.

Variables (genéricas, con fallback a las de sandbox MP_TEST_*):

  MP_ACCESS_TOKEN   access_token MercadoPago  (fallback: MP_TEST_ACCESS_TOKEN)
  MP_PUBLIC_KEY     public_key MercadoPago    (fallback: MP_TEST_PUBLIC_KEY)
  MP_CLIENT_SECRET  clave secreta de webhooks (opcional; fallback:
                    MP_TEST_CLIENT_SECRET)

El modo (Sandbox vs Producción) se deriva del prefijo del access_token:
`TEST-` → Sandbox, `APP_USR-` (u otro) → Producción. Así el mismo comando
sirve para ambos entornos sin cambios de código cuando lleguen las
credenciales productivas.

Idempotente: si ya existe un gateway MERCADOPAGO activo, actualiza sus
credenciales. Si no existe, lo crea.

Uso:
  DJANGO_SETTINGS_MODULE=config.settings.testing python manage.py setup_mp_gateway
  DJANGO_SETTINGS_MODULE=config.settings.testing python manage.py setup_mp_gateway --dry-run
"""
import os

import decouple
from django.core.management.base import BaseCommand, CommandError

from apps.addons.settings_app.models import PaymentGateway


def _read_var(name):
    val = os.environ.get(name)
    if val:
        return val
    try:
        return decouple.config(name)
    except decouple.UndefinedValueError:
        return None


def _read_first(*names):
    """Devuelve el primer valor no vacío entre varias variables (fallback)."""
    for name in names:
        val = _read_var(name)
        if val:
            return val
    return None


class Command(BaseCommand):
    help = 'Crea o actualiza el PaymentGateway de MercadoPago con credenciales de .env'

    # No correr los system checks: en producción (DEBUG=False) el check
    # payments.E001 falla cuando aún no existe el gateway — el estado
    # exacto que este comando viene a resolver (chicken-and-egg). Sin esto,
    # bootstrappear el gateway en una VM nueva exigiría --skip-checks.
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Muestra qué haría sin escribir en la DB',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        access_token = _read_first('MP_ACCESS_TOKEN', 'MP_TEST_ACCESS_TOKEN')
        public_key   = _read_first('MP_PUBLIC_KEY', 'MP_TEST_PUBLIC_KEY')
        client_secret = _read_first('MP_CLIENT_SECRET', 'MP_TEST_CLIENT_SECRET')

        if not access_token or not public_key:
            raise CommandError(
                'Faltan variables MP_ACCESS_TOKEN/MP_PUBLIC_KEY (o los '
                'fallback MP_TEST_ACCESS_TOKEN/MP_TEST_PUBLIC_KEY). '
                'Defínelas en practicayoruba/.env.'
            )

        # El prefijo del access_token determina el modo: TEST- = Sandbox,
        # APP_USR- (u otro) = Producción.
        is_sandbox = access_token.startswith('TEST-')
        modo = 'Sandbox' if is_sandbox else 'Producción'
        name = f'MercadoPago {modo}'

        credentials = {'access_token': access_token, 'public_key': public_key}
        if client_secret:
            credentials['client_secret'] = client_secret

        # No imprimir ningún fragmento del token (ni prefijo): solo modo +
        # últimos 4 enmascarados (BR-009 / RNF-SEC-002). El modo ya se
        # imprime aparte, así que el prefijo del token no aporta nada.
        def _mask(v):
            return ('****' + v[-4:]) if v and len(v) > 4 else '****'
        self.stdout.write(f'modo:          {modo}')
        self.stdout.write(f'access_token:  {_mask(access_token)}')
        self.stdout.write(f'public_key:    {_mask(public_key)}')
        self.stdout.write(
            f'client_secret: {"configurado" if client_secret else "<AUSENTE>"}'
        )

        if dry_run:
            self.stdout.write(self.style.WARNING('--dry-run: sin cambios en DB.'))
            return

        gw, created = PaymentGateway.objects.get_or_create(
            gateway='MERCADOPAGO',
            defaults={'name': name, 'is_active': True},
        )
        gw.is_active = True
        gw.name = name
        gw.set_credentials(credentials)
        gw.save()

        verb = 'Creado' if created else 'Actualizado'
        self.stdout.write(self.style.SUCCESS(
            f'{verb} PaymentGateway id={gw.pk} (MERCADOPAGO, {modo}).'
        ))
