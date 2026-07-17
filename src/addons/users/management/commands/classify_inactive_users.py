"""
classify_inactive_users — herramienta de mantenimiento (FU-1).

Cierra GAP-11 del audit profundo de UC-AUTH-16: la migracion 0006
hizo backfill conservador asignando 'unverified' a TODAS las filas
``users_user`` con ``is_active=False`` previas a la migracion. Si en
produccion habia cuentas suspendidas por admin (UC-AUTH-13)
preexistentes, quedaron mal clasificadas y ResendVerificationView
les ofreceria reactivacion via email — violacion de UC-AUTH-01
Alt-A.3.

Este comando:

  - Lista las cuentas inactivas con ``deactivated_reason='unverified'``.
  - Permite filtrar por fecha (--before, --after) para acotar a la
    ventana previa al deploy de 0006.
  - Permite reclasificar por user.pk a 'suspended' o 'self_deleted'.
  - Modo --dry-run por default (no escribe nada).

Uso tipico:

::

    # 1. Listar candidatos pre-migracion (ajustar fecha al deploy):
    python manage.py classify_inactive_users \\
        --list --before 2026-05-20

    # 2. Reclasificar IDs concretos:
    python manage.py classify_inactive_users \\
        --reclassify 1,5,12 --to suspended --confirm

    # 3. Dry-run de la reclasificacion (default):
    python manage.py classify_inactive_users \\
        --reclassify 1,5,12 --to suspended
    # Imprime el plan; NO escribe.

Refs: GAP-11, DEC-UC16-7.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from addons.users.models import UserDeactivationEvent


User = get_user_model()

VALID_REASONS = {'unverified', 'suspended', 'self_deleted'}


class Command(BaseCommand):
    help = 'Reclasifica deactivated_reason de cuentas inactivas (GAP-11).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--list', action='store_true',
            help='Listar cuentas con deactivated_reason=unverified.',
        )
        parser.add_argument(
            '--before', type=str, default=None,
            help='Filtra deactivated_at < YYYY-MM-DD.',
        )
        parser.add_argument(
            '--after', type=str, default=None,
            help='Filtra deactivated_at >= YYYY-MM-DD.',
        )
        parser.add_argument(
            '--reclassify', type=str, default=None,
            help='Lista de user.pk separados por coma a reclasificar.',
        )
        parser.add_argument(
            '--to', type=str, choices=sorted(VALID_REASONS), default=None,
            help='Causa destino para --reclassify.',
        )
        parser.add_argument(
            '--note', type=str, default='backfill 0006 corregido',
            help='Texto opcional para UserDeactivationEvent.note.',
        )
        parser.add_argument(
            '--confirm', action='store_true',
            help='Aplica el cambio. Sin esta flag corre en dry-run.',
        )

    def handle(self, *args, **opts):
        if opts['list']:
            self._cmd_list(opts)
            return
        if opts['reclassify']:
            self._cmd_reclassify(opts)
            return
        raise CommandError(
            'Especifica --list o --reclassify. --help para detalle.'
        )

    def _cmd_list(self, opts):
        qs = User.objects.filter(
            is_active=False, deactivated_reason='unverified',
        )
        if opts['before']:
            qs = qs.filter(deactivated_at__lt=opts['before'])
        if opts['after']:
            qs = qs.filter(deactivated_at__gte=opts['after'])
        qs = qs.order_by('deactivated_at')

        self.stdout.write(
            f'Cuentas inactivas con reason=unverified: {qs.count()}'
        )
        for u in qs[:100]:
            self.stdout.write(
                f'  pk={u.pk:6d}  {u.email:40s}  '
                f'deactivated_at={u.deactivated_at}'
            )
        if qs.count() > 100:
            self.stdout.write(f'  ... ({qs.count() - 100} mas)')

    def _cmd_reclassify(self, opts):
        if not opts['to']:
            raise CommandError('--to es obligatorio con --reclassify.')

        try:
            pks = [int(s.strip()) for s in opts['reclassify'].split(',') if s.strip()]
        except ValueError as e:
            raise CommandError(f'--reclassify debe ser lista de enteros: {e}')

        if not pks:
            raise CommandError('--reclassify no contiene IDs validos.')

        new_reason = opts['to']
        targets = User.objects.filter(
            pk__in=pks, is_active=False,
        ).exclude(deactivated_reason=new_reason)

        found = list(targets)
        skipped = set(pks) - {u.pk for u in found}

        self.stdout.write(
            f'Plan: reclasificar {len(found)} cuentas a "{new_reason}".'
        )
        if skipped:
            self.stdout.write(self.style.WARNING(
                f'  IDs saltados (ya tienen ese reason o estan activas): '
                f'{sorted(skipped)}'
            ))
        for u in found:
            self.stdout.write(
                f'  pk={u.pk:6d}  {u.email:40s}  '
                f'{u.deactivated_reason} -> {new_reason}'
            )

        if not opts['confirm']:
            self.stdout.write(self.style.NOTICE(
                'DRY-RUN: agrega --confirm para aplicar.'
            ))
            return

        with transaction.atomic():
            now = timezone.now()
            for u in found:
                u.deactivated_reason = new_reason
                u.save(update_fields=['deactivated_reason'])
                # Audit log del fix manual.
                UserDeactivationEvent.objects.create(
                    user=u,
                    reason=new_reason,
                    source=UserDeactivationEvent.SOURCE_ADMIN,
                    actor=None,  # comando shell, sin actor
                    note=f'reclassify (FU-1) — {opts["note"]}',
                )

        self.stdout.write(self.style.SUCCESS(
            f'OK: {len(found)} cuentas reclasificadas.'
        ))
