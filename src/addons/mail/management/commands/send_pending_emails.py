"""
send_pending_emails — management command (Alt 2 DB queue).

Procesa la cola de correo saliente ``mail.mail`` (``MailMail``, hogar Odoo fiel
de la ex-``EmailTask``): filas ``outgoing`` cuya fecha diferida ya pasó, con
backoff exponencial. Ejecutar via cron cada minuto:

    * * * * * cd /path/to/api && python manage.py send_pending_emails

Usa select_for_update(skip_locked=True) para concurrencia segura entre
multiples workers. Cada correo se procesa en su propia transaction atomica.

Backoff: scheduled_date += timedelta(minutes=5 * attempts) tras cada fallo
recuperable; al agotar max_attempts el correo pasa a ``exception`` (terminal).
"""
import logging
from datetime import timedelta

from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.db import transaction

from addons.mail.models import MailMail

logger = logging.getLogger(__name__)

_BATCH_SIZE = 50
_BACKOFF_PER_ATTEMPT = timedelta(minutes=5)


class Command(BaseCommand):
    help = 'Procesa cola de correo saliente mail.mail (Alt 2). Cron cada minuto.'

    def handle(self, *args, **options):
        pending_ids = list(
            MailMail.pending()
            .order_by('scheduled_date', 'id')
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
                mail = (
                    MailMail.objects
                    .select_for_update(skip_locked=True)
                    .get(pk=pk, state=MailMail.STATE_OUTGOING)
                )
            except MailMail.DoesNotExist:
                return 'skipped'

            if mail.attempts >= mail.max_attempts:
                mail.register_failed_attempt(
                    MailMail.FAILURE_MAIL_SMTP, mail.failure_reason,
                )
                return 'failed'

            recipient_list = [e.strip() for e in mail.email_to.split(',') if e.strip()]
            try:
                send_mail(
                    subject=mail.subject,
                    message=mail.body_html,
                    from_email=mail.email_from or None,
                    recipient_list=recipient_list,
                    fail_silently=False,
                )
            except Exception as exc:
                logger.error(
                    'send_pending_emails: mail pk=%s attempt=%s error=%s',
                    pk, mail.attempts + 1, exc,
                )
                mail.register_failed_attempt(
                    MailMail.FAILURE_MAIL_SMTP, str(exc),
                    backoff=_BACKOFF_PER_ATTEMPT * (mail.attempts + 1),
                )
                return 'failed'
            else:
                mail.mark_sent(count_attempt=True)
                return 'sent'
