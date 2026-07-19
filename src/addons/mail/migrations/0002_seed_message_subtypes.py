"""Siembra de subtipos canonicos de mensaje (Odoo ``mail`` data).

Fiel a los registros de datos de Odoo ``mail/data/mail_data.xml``:
``mail.mt_comment`` ("Discussions", publico, default) y ``mail.mt_note``
("Note", interno, hidden). Idempotente (``update_or_create`` por ``name`` con
``res_model=''``); reversible.
"""
from django.db import migrations


CANONICAL_SUBTYPES = [
    {'name': 'Discussions', 'internal': False, 'default': True,
     'hidden': False, 'sequence': 1, 'description': ''},
    {'name': 'Note', 'internal': True, 'default': False,
     'hidden': True, 'sequence': 2, 'description': ''},
]


def seed_subtypes(apps, schema_editor):
    MailMessageSubtype = apps.get_model('mail', 'MailMessageSubtype')
    for spec in CANONICAL_SUBTYPES:
        MailMessageSubtype.objects.update_or_create(
            name=spec['name'], res_model='',
            defaults={
                'internal': spec['internal'],
                'default': spec['default'],
                'hidden': spec['hidden'],
                'sequence': spec['sequence'],
                'description': spec['description'],
            },
        )


def unseed_subtypes(apps, schema_editor):
    MailMessageSubtype = apps.get_model('mail', 'MailMessageSubtype')
    names = [spec['name'] for spec in CANONICAL_SUBTYPES]
    MailMessageSubtype.objects.filter(name__in=names, res_model='').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('mail', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_subtypes, unseed_subtypes),
    ]
