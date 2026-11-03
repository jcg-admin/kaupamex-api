"""Siembra ``_DEFAULT_PARAMETERS`` — ≙ el ``post_init`` de ``base``.

La fuente llama ``env['ir.config_parameter'].init(force=True)`` al instalar
``base`` (``odoo19c: odoo/addons/base/__init__.py:9-11``). Aquí nadie lo
llamaba fuera de ``tests/conftest.py``: medido sobre una base creada sólo con
``migrate``, ``system_parameter`` tenía los 15 parámetros de addon y ninguno
de ``_DEFAULT_PARAMETERS`` — sin ``database.secret``, ``tools.misc.hmac`` no
puede firmar. Es la forma de H-API-263: la migración del spec se perdió y sólo
sobrevivió ``seed()``.

Importa **el spec**, no ``init()``, y escribe sobre el modelo histórico, como
las siembras de los addons. Crea sólo las claves ausentes: en una base que ya
las tiene, rotar ``database.secret`` invalidaría todo token firmado, y el
``force=True`` de la fuente corre en la instalación, donde no hay nada que
pisar.
"""

from django.db import migrations

from addons.base.models.ir_config_parameter import _DEFAULT_PARAMETERS


def seed(apps, schema_editor):
    """Crea las claves ausentes del spec sobre el modelo histórico."""
    SystemParameter = apps.get_model('base', 'SystemParameter')
    alias = schema_editor.connection.alias
    for key, func in _DEFAULT_PARAMETERS.items():
        if not SystemParameter.objects.using(alias).filter(key=key).exists():
            SystemParameter.objects.using(alias).create(key=key, value=str(func()))


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0093_json_nullable_by_default'),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
