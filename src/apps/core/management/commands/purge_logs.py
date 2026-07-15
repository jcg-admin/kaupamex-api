"""
apps/core/management/commands/purge_logs.py

purge_logs (SOL-011 T-07, DEC-LOG-05): purga por retencion de las tablas de
logging, corrida por cron. Sin retencion las tablas crecen sin limite (gap de
django-db-logger). Idempotente: si no hay filas vencidas, borra 0.

Politica ratificada (2026-07-09):
  - RequestLog:            30 dias
  - AppLog INFO/DEBUG:     14 dias
  - AppLog WARNING/ERROR/CRITICAL: 90 dias
  - BusinessEvent:         NO lo purga este comando (append-only de negocio).

Uso:
  manage.py purge_logs            # ejecuta la purga
  manage.py purge_logs --dry-run  # solo reporta cuantas filas se purgarian
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.core.models import AppLog, RequestLog


class Command(BaseCommand):
    help = 'Purga RequestLog/AppLog por retencion (DEC-LOG-05). BusinessEvent no se toca.'

    REQUESTLOG_DAYS = 30
    APPLOG_LOW_DAYS = 14   # INFO / DEBUG
    APPLOG_HIGH_DAYS = 90  # WARNING / ERROR / CRITICAL
    _LOW_LEVELS = ['DEBUG', 'INFO']
    _HIGH_LEVELS = ['WARNING', 'ERROR', 'CRITICAL']

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='No borra; solo reporta cuantas filas se purgarian.',
        )

    def handle(self, *args, **options):
        now = timezone.now()
        dry = options['dry_run']

        request_qs = RequestLog.objects.filter(
            created_at__lt=now - timedelta(days=self.REQUESTLOG_DAYS))
        low_qs = AppLog.objects.filter(
            level__in=self._LOW_LEVELS,
            created_at__lt=now - timedelta(days=self.APPLOG_LOW_DAYS))
        high_qs = AppLog.objects.filter(
            level__in=self._HIGH_LEVELS,
            created_at__lt=now - timedelta(days=self.APPLOG_HIGH_DAYS))

        counts = {
            'RequestLog': request_qs.count(),
            'AppLog INFO/DEBUG': low_qs.count(),
            'AppLog WARNING/ERROR': high_qs.count(),
        }

        if not dry:
            request_qs.delete()
            low_qs.delete()
            high_qs.delete()

        prefix = '[dry-run] ' if dry else ''
        for label, n in counts.items():
            self.stdout.write(f'{prefix}{label}: {n} filas '
                              f'{"a purgar" if dry else "purgadas"}')
        total = sum(counts.values())
        self.stdout.write(self.style.SUCCESS(
            f'{prefix}Total: {total} filas '
            f'{"a purgar" if dry else "purgadas"}'))
