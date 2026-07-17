"""Siembra ``_DEFAULT_PARAMETERS`` al crear la instancia (Odoo ``init``).

Fiel a Odoo: los defaults se crean cuando nace la BD. Se usa el modelo histórico
(``apps.get_model``) y el dict de callables importado del módulo (valores
``uuid`` puros, sin dependencia del ORM). Idempotente: sólo crea las ausentes.
"""
from django.db import migrations

from apps.base.models import _DEFAULT_PARAMETERS


def seed_defaults(apps, schema_editor):
    SystemParameter = apps.get_model('base', 'SystemParameter')
    db = schema_editor.connection.alias
    for key, func in _DEFAULT_PARAMETERS.items():
        if not SystemParameter.objects.using(db).filter(key=key).exists():
            SystemParameter.objects.using(db).create(key=key, value=str(func()))


def unseed_defaults(apps, schema_editor):
    SystemParameter = apps.get_model('base', 'SystemParameter')
    db = schema_editor.connection.alias
    SystemParameter.objects.using(db).filter(
        key__in=list(_DEFAULT_PARAMETERS)).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_defaults, unseed_defaults),
    ]
