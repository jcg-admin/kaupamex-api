"""Siembra la política de contraseña L2 (``authz.password_minlength``).

Adaptación nativa de ``odoo19c: addons/auth_password_policy/data/defaults.xml``,
que siembra ``auth_password_policy.minlength``. Mismo patrón idempotente que
``base.0003``: sólo crea la clave si está ausente. El valor por defecto (8)
preserva el comportamiento previo (``MinimumLengthValidator`` de Django cableaba
8), ahora editable en caliente en ``SystemParameter`` (L2).

**Por qué se re-crea.** Esta migración existió en ``auth_password_policy`` y se
perdió al retirar el addon ``orders`` (``api@77bd1f0``); el rename a
``authz_password_policy`` no la trajo de vuelta porque ``makemigrations`` sólo
regenera lo que deriva de un cambio de modelo, y una data-migration no deriva de
ninguno. Sin ella ``SystemParameter.get_param('authz.password_minlength')``
devuelve ``None`` y el validador queda inerte — que es lo contrario de lo que
declara ``validators.py``.
"""
from django.db import migrations

from addons.authz_password_policy.data import PASSWORD_POLICY_PARAMETERS


def seed_password_policy(apps, schema_editor):
    SystemParameter = apps.get_model('base', 'SystemParameter')
    db = schema_editor.connection.alias
    for key, value in PASSWORD_POLICY_PARAMETERS.items():
        if not SystemParameter.objects.using(db).filter(key=key).exists():
            SystemParameter.objects.using(db).create(key=key, value=value)


def unseed_password_policy(apps, schema_editor):
    SystemParameter = apps.get_model('base', 'SystemParameter')
    db = schema_editor.connection.alias
    SystemParameter.objects.using(db).filter(
        key__in=list(PASSWORD_POLICY_PARAMETERS)).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_password_policy, unseed_password_policy),
    ]
