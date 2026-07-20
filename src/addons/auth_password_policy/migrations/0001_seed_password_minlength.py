"""Siembra la política de contraseña L2 (``authz.password_minlength``).

Adaptación nativa de ``auth_password_policy/data/defaults.xml`` de Odoo, que
siembra ``auth_password_policy.minlength``. Mismo patrón idempotente que
``base.0003``: sólo crea la clave si está ausente. El valor por defecto (8)
preserva el comportamiento previo (``MinimumLengthValidator`` de Django cableaba
8), ahora editable en caliente en ``SystemParameter`` (L2).
"""
from django.db import migrations

_KEY = 'authz.password_minlength'
_DEFAULT = '8'


def seed_password_policy(apps, schema_editor):
    SystemParameter = apps.get_model('base', 'SystemParameter')
    db = schema_editor.connection.alias
    if not SystemParameter.objects.using(db).filter(key=_KEY).exists():
        SystemParameter.objects.using(db).create(key=_KEY, value=_DEFAULT)


def unseed_password_policy(apps, schema_editor):
    SystemParameter = apps.get_model('base', 'SystemParameter')
    db = schema_editor.connection.alias
    SystemParameter.objects.using(db).filter(key=_KEY).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_password_policy, unseed_password_policy),
    ]
