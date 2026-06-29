"""
setup_mp_gateway — crea o actualiza el PaymentGateway de MercadoPago.

Lee las credenciales de sandbox desde variables de entorno (con fallback
a decouple/.env) y guarda el registro PaymentGateway cifrado en la DB.

Variables requeridas (definidas en practicayoruba/.env):

  MP_TEST_ACCESS_TOKEN   access_token de sandbox MercadoPago
  MP_TEST_PUBLIC_KEY     public_key de sandbox MercadoPago

Idempotente: si ya existe un gateway MERCADOPAGO activo, actualiza sus
credenciales. Si no existe, lo crea.

Uso:
  DJANGO_SETTINGS_MODULE=config.settings.testing python manage.py setup_mp_gateway
  DJANGO_SETTINGS_MODULE=config.settings.testing python manage.py setup_mp_gateway --dry-run
"""
import os

import decouple
from django.core.management.base import BaseCommand, CommandError

from apps.settings_app.models import PaymentGateway


def _read_var(name):
    val = os.environ.get(name)
    if val:
        return val
    try:
        return decouple.config(name)
    except decouple.UndefinedValueError:
        return None


class Command(BaseCommand):
    help = 'Crea o actualiza el PaymentGateway de MercadoPago con credenciales de .env'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Muestra qué haría sin escribir en la DB',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        access_token = _read_var('MP_TEST_ACCESS_TOKEN')
        public_key   = _read_var('MP_TEST_PUBLIC_KEY')

        if not access_token or not public_key:
            raise CommandError(
                'Faltan variables MP_TEST_ACCESS_TOKEN y/o MP_TEST_PUBLIC_KEY. '
                'Defínelas en practicayoruba/.env.'
            )

        self.stdout.write(f'access_token: {access_token[:20]}…')
        self.stdout.write(f'public_key:   {public_key[:20]}…')

        if dry_run:
            self.stdout.write(self.style.WARNING('--dry-run: sin cambios en DB.'))
            return

        gw, created = PaymentGateway.objects.get_or_create(
            gateway='MERCADOPAGO',
            defaults={'name': 'MercadoPago Sandbox', 'is_active': True},
        )
        gw.is_active = True
        gw.set_credentials({'access_token': access_token, 'public_key': public_key})
        gw.save()

        verb = 'Creado' if created else 'Actualizado'
        self.stdout.write(self.style.SUCCESS(f'{verb} PaymentGateway id={gw.pk} (MERCADOPAGO).'))
