"""
create_seed_users — seed de usuarios E2E (iniciativa seed-usuarios-e2e).

Crea (o actualiza idempotentemente) el superusuario admin y el
comprador QA para pruebas E2E. Las credenciales se leen desde variables
de entorno (os.environ, cargado por bootstrap.sh via 'set -a; source
.env; set +a') con fallback a decouple (carga .env del proyecto) para
invocación manual directa.

Variables requeridas (definidas en practicayoruba/.env):

  ADMIN_EMAIL       email del superusuario admin
  ADMIN_USERNAME    username del superusuario admin
  ADMIN_PASSWORD    password del superusuario admin
  QA_BUYER_EMAIL    email del comprador QA
  QA_BUYER_PASSWORD password del comprador QA

El username del comprador QA es siempre "qabuyer".

Idempotente: si el usuario ya existe, actualiza email, flags y password.
Exit 0 en todos los casos (nuevo o actualizado).

Uso:
  python manage.py create_seed_users
  python manage.py create_seed_users --dry-run
"""
import os

import decouple
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.authz.models import Role, RoleAssignment
from apps.authz.services import SUPERADMIN_ROLE_CODE


User = get_user_model()

_REQUIRED_VARS = (
    'ADMIN_EMAIL',
    'ADMIN_USERNAME',
    'ADMIN_PASSWORD',
    'QA_BUYER_EMAIL',
    'QA_BUYER_PASSWORD',
)

QA_BUYER_USERNAME = 'qabuyer'


def _read_var(name):
    """Leer variable de entorno con fallback a decouple (lee .env)."""
    val = os.environ.get(name)
    if val:
        return val
    try:
        # Acceso via modulo (no `from decouple import config`) para que el
        # fallback se resuelva en cada llamada y los tests puedan parchear
        # `decouple.config` con monkeypatch (H-API-04).
        return decouple.config(name, default=None)
    except Exception:
        return None


class Command(BaseCommand):
    help = 'Seed de usuarios E2E: superusuario admin + comprador QA.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Muestra el plan sin escribir en la base de datos.',
        )

    def handle(self, *args, **opts):
        dry_run = opts['dry_run']

        vals = {}
        missing = []
        for var in _REQUIRED_VARS:
            val = _read_var(var)
            if val:
                vals[var] = val
            else:
                missing.append(var)

        if missing:
            raise CommandError(
                'Variables de entorno faltantes: {}. '
                'Definirlas en practicayoruba/.env antes de ejecutar '
                'este comando.'.format(', '.join(missing))
            )

        if dry_run:
            self.stdout.write(self.style.NOTICE('DRY-RUN — no se escribe nada.'))
            self.stdout.write(
                '  Admin    : {} <{}>'.format(
                    vals['ADMIN_USERNAME'], vals['ADMIN_EMAIL']
                )
            )
            self.stdout.write(
                '  QA Buyer : {} <{}>'.format(
                    QA_BUYER_USERNAME, vals['QA_BUYER_EMAIL']
                )
            )
            return

        with transaction.atomic():
            admin, admin_created = _upsert_admin(vals)
            buyer, buyer_created = _upsert_qa_buyer(vals)

        self.stdout.write(self.style.SUCCESS(
            'Admin    : {} <{}> — {}'.format(
                admin.email, admin.email,
                'creado' if admin_created else 'actualizado',
            )
        ))
        self.stdout.write(self.style.SUCCESS(
            'QA Buyer : {} <{}> — {}'.format(
                buyer.email, buyer.email,
                'creado' if buyer_created else 'actualizado',
            )
        ))


def _upsert_admin(vals):
    # Party (T-201): email es el identificador (USERNAME_FIELD). ``is_staff``/
    # ``is_superuser`` ya no existen — el acceso admin se otorga con el rol
    # ``superadmin`` de apps.authz (DEC-01=B). Lookup por email; idempotente.
    email = vals['ADMIN_EMAIL']
    user, created = User.objects.update_or_create(
        email=email,
        defaults={
            'is_active': True,
            'deactivated_reason': None,
            'deactivated_at': None,
        },
    )
    user.set_password(vals['ADMIN_PASSWORD'])
    user.save(update_fields=['password'])
    role, _ = Role.objects.get_or_create(
        code=SUPERADMIN_ROLE_CODE, defaults={'name': 'Superadministrador'},
    )
    RoleAssignment.objects.get_or_create(user=user, role=role)
    return user, created


def _upsert_qa_buyer(vals):
    # Comprador seed: identidad party sin rol admin (email es el identificador).
    email = vals['QA_BUYER_EMAIL']
    user, created = User.objects.update_or_create(
        email=email,
        defaults={
            'is_active': True,
            'deactivated_reason': None,
            'deactivated_at': None,
        },
    )
    user.set_password(vals['QA_BUYER_PASSWORD'])
    user.save(update_fields=['password'])
    return user, created
