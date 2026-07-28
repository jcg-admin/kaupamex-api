"""Siembra las banderas de auto-registro / reset L2 (authz_signup).

Adaptación de los config-params de ``auth_signup`` de Odoo
(``auth_signup.invitation_scope`` / ``auth_signup.reset_password``). Mismo
patrón idempotente que ``base.0003``: sólo crea las claves ausentes. Ambas se
siembran **abiertas** ('1'), preservando el comportamiento previo (registro y
reset públicos), ahora editables en caliente en ``SystemParameter`` (L2).
"""
from django.db import migrations

from addons.auth_signup.data import SIGNUP_PARAMETERS as _KEYS


def seed_signup_flags(apps, schema_editor):
    SystemParameter = apps.get_model('base', 'SystemParameter')
    db = schema_editor.connection.alias
    for key, value in _KEYS.items():
        if not SystemParameter.objects.using(db).filter(key=key).exists():
            SystemParameter.objects.using(db).create(key=key, value=value)


def unseed_signup_flags(apps, schema_editor):
    SystemParameter = apps.get_model('base', 'SystemParameter')
    db = schema_editor.connection.alias
    SystemParameter.objects.using(db).filter(key__in=list(_KEYS)).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_signup_flags, unseed_signup_flags),
    ]
