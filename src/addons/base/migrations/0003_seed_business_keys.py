"""Siembra las claves de negocio L2 migradas desde ``config.settings.base``
(slice 2 de ``implementar-systemparameter-l2``; cierra el drift H-API-CFG-01/02
de :ref:`hallazgos-estrategia-configuracion-kaupamex`).

``AUTHZ_REAUTH_TTL`` y ``BACKUP_ALERT_EMAIL`` dejan de leerse de
``config.settings.base`` con ``default=`` cableado y pasan a
``SystemParameter`` (``authz.reauth_ttl`` / ``backup.alert_email``). Reusa el
mismo patrón idempotente de ``0002_seed_default_parameters``: sólo crea las
claves ausentes. En una BD que ya corrió ``0002`` (que sólo conocía
``database.uuid``/``database.secret``), esta migración es la que efectivamente
crea las dos claves nuevas — ``0002`` no las re-siembra porque itera sobre el
dict `_DEFAULT_PARAMETERS` **al momento en que corrió**, no al estado actual
del módulo.
"""
from django.db import migrations

from addons.base.models import _DEFAULT_PARAMETERS

_NEW_KEYS = ('authz.reauth_ttl', 'backup.alert_email')


def seed_business_keys(apps, schema_editor):
    SystemParameter = apps.get_model('base', 'SystemParameter')
    db = schema_editor.connection.alias
    for key in _NEW_KEYS:
        func = _DEFAULT_PARAMETERS[key]
        if not SystemParameter.objects.using(db).filter(key=key).exists():
            SystemParameter.objects.using(db).create(key=key, value=str(func()))


def unseed_business_keys(apps, schema_editor):
    SystemParameter = apps.get_model('base', 'SystemParameter')
    db = schema_editor.connection.alias
    SystemParameter.objects.using(db).filter(key__in=list(_NEW_KEYS)).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0002_seed_default_parameters'),
    ]

    operations = [
        migrations.RunPython(seed_business_keys, unseed_business_keys),
    ]
