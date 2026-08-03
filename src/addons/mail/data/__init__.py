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


def seed(using=DEFAULT_DB_ALIAS):
    """Reinstala los subtipos canónicos (``update_or_create`` por nombre)."""
    for spec in CANONICAL_SUBTYPES:
        MailMessageSubtype.objects.using(using).update_or_create(
            name=spec['name'], res_model='',
            defaults={k: v for k, v in spec.items() if k != 'name'},
        )
