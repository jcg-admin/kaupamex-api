"""Siembra las banderas de auto-registro / reset L2 (``authz_signup``).

Adaptación de los config-params de ``odoo19c: addons/auth_signup``
(``auth_signup.invitation_scope`` / ``auth_signup.reset_password``). Mismo
patrón idempotente que ``base.0003``: sólo crea las claves ausentes. Ambas se
siembran **abiertas** ('1'), preservando el comportamiento previo (registro y
reset públicos), ahora editables en caliente en ``SystemParameter`` (L2).

**Por qué se re-crea.** Igual que ``authz_password_policy.0001``: la migración
existía y se perdió en un retiro de addon; ``makemigrations`` no la regenera
porque una data-migration no deriva de ningún cambio de modelo. Sin ella las
dos banderas no existen y ``get_signup_policy()`` lee ``None``.

El spec vive en ``data.py`` — una sola fuente para el arranque (esta migración)
y para la re-aplicación sobre el modelo vivo (``seed()``, H-API-22).
"""
from django.db import migrations

from addons.authz_signup.data import SIGNUP_PARAMETERS


def seed_signup_flags(apps, schema_editor):
    SystemParameter = apps.get_model('base', 'SystemParameter')
    db = schema_editor.connection.alias
    for key, value in SIGNUP_PARAMETERS.items():
        if not SystemParameter.objects.using(db).filter(key=key).exists():
            SystemParameter.objects.using(db).create(key=key, value=value)


def unseed_signup_flags(apps, schema_editor):
    SystemParameter = apps.get_model('base', 'SystemParameter')
    db = schema_editor.connection.alias
    SystemParameter.objects.using(db).filter(
        key__in=list(SIGNUP_PARAMETERS)).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_signup_flags, unseed_signup_flags),
    ]
