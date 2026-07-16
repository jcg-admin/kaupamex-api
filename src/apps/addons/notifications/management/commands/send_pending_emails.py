"""
send_pending_emails — management command (Alt 2 DB queue).

Procesa filas PENDING/RETRYING de EmailTask con backoff exponencial.
Ejecutar via cron cada minuto:

    * * * * * cd /path/to/api && python manage.py send_pending_emails

Usa select_for_update(skip_locked=True) para concurrencia segura entre
multiples workers. Cada tarea se procesa en su propia transaction atomica.

Backoff: scheduled_at += timedelta(minutes=5 * attempts) tras cada fallo.
"""
import logging
from datetime import timedelta

from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.addons.notifications.models import EmailTask

logger = logging.getLogger(__name__)

_BATCH_SIZE = 50


class Command(BaseCommand):
    help = 'Procesa cola de emails pendientes (Alt 2). Ejecutar via cron cada minuto.'

    def handle(self, *args, **options):
        pending_ids = list(
            EmailTask.objects
            .filter(
                status__in=[EmailTask.Status.PENDING, EmailTask.Status.RETRYING],
                scheduled_at__lte=timezone.now(),
            )
            .order_by('scheduled_at')
            .values_list('pk', flat=True)[:_BATCH_SIZE]
        )

        sent = failed = skipped = 0
        for pk in pending_ids:
            result = self._process(pk)
            if result == 'sent':
                sent += 1
            elif result == 'failed':
                failed += 1
            else:
                skipped += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'send_pending_emails: sent={sent} failed={failed} skipped={skipped}'
            )
        )

    def _process(self, pk):
        with transaction.atomic():
            try:
                task = (
                    EmailTask.objects
                    .select_for_update(skip_locked=True)
                    .get(
                        pk=pk,
                        status__in=[EmailTask.Status.PENDING, EmailTask.Status.RETRYING],
                    )
                )
            except EmailTask.DoesNotExist:
                return 'skipped'

            if task.attempts >= task.max_attempts:
                task.status = EmailTask.Status.FAILED
                task.save(update_fields=['status', 'updated_at'])
                return 'failed'

            task.attempts += 1
            try:
                recipient_list = [e.strip() for e in task.to.split(',') if e.strip()]
                send_mail(
                    subject=task.subject,
                    message=task.body,
                    from_email=task.from_email or None,
                    recipient_list=recipient_list,
                    fail_silently=False,
                )
                task.status = EmailTask.Status.SENT
                task.sent_at = timezone.now()
                task.save(update_fields=['status', 'sent_at', 'attempts', 'updated_at'])
                return 'sent'
            except Exception as exc:
                logger.error('send_pending_emails: task pk=%s attempt=%s error=%s', pk, task.attempts, exc)
                task.last_error = str(exc)[:500]
                if task.attempts >= task.max_attempts:
                    task.status = EmailTask.Status.FAILED
                else:
                    task.status = EmailTask.Status.RETRYING
                    task.scheduled_at = timezone.now() + timedelta(minutes=5 * task.attempts)
                task.save(update_fields=['status', 'last_error', 'attempts', 'scheduled_at', 'updated_at'])
                return 'failed'
