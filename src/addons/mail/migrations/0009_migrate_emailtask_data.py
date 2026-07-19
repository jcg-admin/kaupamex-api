"""Migracion de datos: ``notifications.EmailTask`` → ``mail.mail`` (slice 2 de
la disolucion ``notifications``→``mail``).

Copia la cola de correo saliente del addon de proyecto ``notifications`` (en
disolucion) a su hogar Odoo ``mail.mail`` **sin perdida**, antes de retirar
``EmailTask``:

- ``EmailTask`` → ``MailMail``. El estado ``pending``/``retrying`` mapea a
  ``outgoing`` (la cola de reintento son filas ``outgoing``), ``sent`` a
  ``sent``, ``failed`` (max reintentos) a ``exception``. Los campos de payload
  y de reintento se preservan: ``to``/``subject``/``body``/``from_email`` →
  ``email_to``/``subject``/``body_html``/``email_from``; ``last_error`` →
  ``failure_reason``; ``attempts``/``max_attempts`` y ``scheduled_at`` →
  ``scheduled_date`` intactos.

Idempotente: no re-copia si ya existe un ``MailMail`` con el mismo
``email_to``/``subject``/``scheduled_date``. Reversible parcialmente (borra lo
copiado que aun sigue ``outgoing`` sin intentos). En la BD de test la tabla
``notifications_emailtask`` esta vacia → no copia nada; en prod copia la cola
real antes de retirar ``EmailTask``.
"""
from django.db import migrations

_STATUS_TO_STATE = {
    'pending': 'outgoing',
    'retrying': 'outgoing',
    'sent': 'sent',
    'failed': 'exception',
}


def forwards(apps, schema_editor):
    try:
        EmailTask = apps.get_model('notifications', 'EmailTask')
    except LookupError:
        return
    MailMail = apps.get_model('mail', 'MailMail')

    for task in EmailTask.objects.all():
        state = _STATUS_TO_STATE.get(task.status, 'outgoing')
        MailMail.objects.get_or_create(
            email_to=task.to,
            subject=task.subject,
            scheduled_date=task.scheduled_at,
            defaults={
                'body_html': task.body,
                'email_from': task.from_email,
                'state': state,
                'failure_reason': task.last_error or '',
                'attempts': task.attempts,
                'max_attempts': task.max_attempts,
            },
        )


def backwards(apps, schema_editor):
    # No hay clave natural para revertir con precision; borra solo las filas
    # outgoing sin intentos (las recien copiadas de una cola pending intacta).
    MailMail = apps.get_model('mail', 'MailMail')
    MailMail.objects.filter(state='outgoing', attempts=0).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('mail', '0008_remove_mailnotification_email_task_and_more'),
        ('notifications', '0002_notification_mail_message'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
