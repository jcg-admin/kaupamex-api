"""Datos semilla del addon — equivalente nativo de ``data/mail_data.xml``.

Fiel a los registros de Odoo ``mail/data/mail_data.xml``: ``mail.mt_comment``
("Discussions", público, default) y ``mail.mt_note`` ("Note", interno, hidden).

Spec único que consumen la data-migration ``0002_seed_message_subtypes``
(arranque) y ``seed()`` (re-aplicación sobre el modelo vivo, H-API-22).
"""
from django.db import DEFAULT_DB_ALIAS

from addons.mail.models import MailMessageSubtype

CANONICAL_SUBTYPES = [
    {'name': 'Discussions', 'internal': False, 'default': True,
     'hidden': False, 'sequence': 1, 'description': ''},
    {'name': 'Note', 'internal': True, 'default': False,
     'hidden': True, 'sequence': 2, 'description': ''},
]

# Equivalente de ``ir_cron_mail_scheduler_action`` (``odoo19c: mail/data/
# ir_cron_data.xml:4-13``, ``odoo-tools@622ddc2a``), cuyo cuerpo es
# ``model.process_email_queue(batch_size=1000)`` con ``interval_type=hours``
# y ``priority=6``.
#
# Divergencia declarada en el intervalo: la referencia corre la cola **cada
# hora**; aquí cada **minuto**, que es lo que el comando suelto ya prescribía
# en su docstring ("Cron cada minuto") desde antes de existir ir.cron. Un
# correo transaccional —verificación de cuenta, restablecimiento de
# contraseña— con hasta una hora de retraso no sirve para lo que se emitió.
CRON_EMAIL_QUEUE = {
    'name': 'Mail: gestor de la cola de correo',
    'model_name': 'mail.MailMail',
    'method_name': 'process_email_queue',
    'interval_number': 1,
    'interval_type': 'minutes',
    'priority': 6,
}


def seed(using=DEFAULT_DB_ALIAS):
    """Reinstala los subtipos canónicos (``update_or_create`` por nombre)."""
    for spec in CANONICAL_SUBTYPES:
        MailMessageSubtype.objects.using(using).update_or_create(
            name=spec['name'], res_model='',
            defaults={k: v for k, v in spec.items() if k != 'name'},
        )
