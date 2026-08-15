"""Siembra inicial del addon ``utm`` — la data-migration que su ``data`` declara.

Escribe sobre el modelo **histórico** (``apps.get_model``), no sobre el vivo:
una migración no ejecuta comportamiento de la app, que cambia bajo sus pies.
Por eso el nombre se graba tal cual y **no** pasa por el contador ``[N]`` de
``save()`` — la semilla no colisiona consigo misma, y la fuente tampoco la
numera (su XML escribe el valor literal).

Idempotente y ``noupdate`` como el XML de la referencia: nunca pisa un valor
que ya exista. La clave de idempotencia es el **identificador externo**
(``module``, ``name`` de ``ir.model.data``), que es la que la fuente usa.
"""
from django.db import migrations

from addons.utm.data import UTM_MEDIUMS, UTM_SOURCES, UTM_STAGES, UTM_TAGS


def _seed(apps, alias, model_name, specs):
    """Crea cada registro y graba su identificador externo, si no existía."""
    model = apps.get_model('utm', model_name)
    ir_model_data = apps.get_model('base', 'IrModelData')
    label = f'utm.{model_name}'

    for spec in specs:
        module, _, name = spec['xmlid'].partition('.')
        already = ir_model_data.objects.using(alias).filter(
            module=module, name=name).first()
        if already is not None:
            continue
        values = {k: v for k, v in spec.items() if k != 'xmlid'}
        record = model.objects.using(alias).create(**values)
        ir_model_data.objects.using(alias).create(
            module=module, name=name, model=label,
            res_id=record.pk, noupdate=True,
        )


def sembrar(apps, schema_editor):
    alias = schema_editor.connection.alias
    _seed(apps, alias, 'UtmStage', UTM_STAGES)
    _seed(apps, alias, 'UtmMedium', UTM_MEDIUMS)
    _seed(apps, alias, 'UtmSource', UTM_SOURCES)
    _seed(apps, alias, 'UtmTag', UTM_TAGS)


class Migration(migrations.Migration):

    dependencies = [
        ('utm', '0001_initial'),
        ('base', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(sembrar, migrations.RunPython.noop),
    ]
