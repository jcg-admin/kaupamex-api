"""Renombra el octavo tipo de vista: ``qweb`` → ``template`` (DEC-FW-05, pieza 5).

El valor nombraba al **intérprete**, no a la cosa; los otros siete nombran qué
es la vista. Es el mismo par que ``report_type`` ya resolvió al retirar el
prefijo ``qweb-`` (``ir_actions_report.py:146-152``). El nombre nuevo no se
inventa: es el que la referencia usa en la superficie que un humano escribe —
``<template id="...">``, manejador ``_tag_template``
(``odoo19c: odoo/tools/convert.py:469,655``).

**Tres pasos, y el orden importa.** La restricción vieja nombra el valor viejo
en su condición: si el dato se renombrara con la restricción puesta, PostgreSQL
la evaluaría contra filas que ya no la satisfacen por el nombre. Se retira, se
renombra el dato, y se vuelve a poner con la condición nueva.
"""
from django.db import migrations, models


def qweb_to_template(apps, schema_editor):
    """Renombra el valor en las filas ya guardadas."""
    IrUiView = apps.get_model('base', 'IrUiView')
    alias = schema_editor.connection.alias
    IrUiView.objects.using(alias).filter(type='qweb').update(type='template')


def template_to_qweb(apps, schema_editor):
    """El reverse, simétrico — la migración es reversible sin pérdida."""
    IrUiView = apps.get_model('base', 'IrUiView')
    alias = schema_editor.connection.alias
    IrUiView.objects.using(alias).filter(type='template').update(type='qweb')


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0069_ir_actions_report_group_ids_and_paperformat_id'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='iruiview',
            name='ir_ui_view_qweb_required_key',
        ),
        migrations.RunPython(qweb_to_template, template_to_qweb),
        migrations.AlterField(
            model_name='iruiview',
            name='type',
            field=models.CharField(
                blank=True, default='', max_length=16,
                verbose_name='Tipo de vista',
                choices=[
                    ('list', 'Lista'),
                    ('form', 'Formulario'),
                    ('graph', 'Gráfica'),
                    ('pivot', 'Tabla dinámica'),
                    ('calendar', 'Calendario'),
                    ('kanban', 'Kanban'),
                    ('search', 'Búsqueda'),
                    ('template', 'Plantilla'),
                ],
            ),
        ),
        migrations.AddConstraint(
            model_name='iruiview',
            constraint=models.CheckConstraint(
                condition=~models.Q(type='template') | ~models.Q(key=''),
                name='ir_ui_view_template_required_key',
            ),
        ),
    ]
