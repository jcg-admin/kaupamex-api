"""Siembra de subtipos canonicos de mensaje (Odoo ``mail`` data).

Fiel a los registros de datos XML de Odoo ``mail/data/mail_data.xml``:

- ``mail.mt_comment`` — "Discussions": el subtipo de los comentarios/mensajes
  publicos del chatter. ``internal=False`` (lo reciben todos los seguidores),
  ``default=True`` (activo al seguir).
- ``mail.mt_note`` — "Note": nota interna, ``internal=True`` (solo empleados
  internos), ``default=False``, ``hidden=True`` (no se ofrece en las
  preferencias del seguidor).

Idempotente: ``update_or_create`` por ``name`` con ``res_model=''`` (aplican a
todos los modelos). Reversible: elimina exactamente esas dos filas.
"""
from django.db import migrations


CANONICAL_SUBTYPES = [
    {
        'name': 'Discussions',
        'internal': False,
        'default': True,
        'hidden': False,
        'sequence': 1,
        'description': '',
    },
    {
        'name': 'Note',
        'internal': True,
        'default': False,
        'hidden': True,
        'sequence': 2,
        'description': '',
    },
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
        ('mail', '0005_mailnotification'),
    ]

    operations = [
        migrations.RunPython(seed_subtypes, unseed_subtypes),
    ]
