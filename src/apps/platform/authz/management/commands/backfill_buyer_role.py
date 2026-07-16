"""Backfill idempotente del rol 'comprador' (DEC-AUTHZ-BUYER).

Asigna el rol ``comprador`` a todo usuario que aún no lo tenga, para que su menú
de cuenta dinámico (``audience='account'``) aparezca. Se corre una vez tras
introducir el rol; es re-ejecutable sin duplicar (``get_or_create``). Requiere
``seed_authz`` antes (el rol debe existir).

Uso: ``python manage.py backfill_buyer_role``.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.platform.authz.models import Role, RoleAssignment
from apps.platform.authz.services import BUYER_ROLE_CODE, invalidate_capabilities

User = get_user_model()


class Command(BaseCommand):
    help = "Asigna el rol 'comprador' a los usuarios que no lo tengan."

    def handle(self, *args, **options):
        role = Role.objects.filter(code=BUYER_ROLE_CODE).first()
        if role is None:
            self.stderr.write(
                "Rol 'comprador' no existe. Corre 'seed_authz' primero."
            )
            return

        already = set(
            RoleAssignment.objects.filter(role=role)
            .values_list('user_id', flat=True)
        )
        pending = User.objects.exclude(pk__in=already).values_list('pk', flat=True)

        n = 0
        for user_id in pending:
            RoleAssignment.objects.get_or_create(user_id=user_id, role=role)
            invalidate_capabilities(user_id)
            n += 1

        self.stdout.write(self.style.SUCCESS(
            f"backfill_buyer_role OK: {n} usuarios asignados al rol 'comprador'."
        ))
