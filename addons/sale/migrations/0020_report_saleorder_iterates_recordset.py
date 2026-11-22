"""El descriptor sembrado del reporte recorre ``order_line`` como recordset.

``sale.order`` adopta ``BaseModel`` y ``order.order_line`` deja de ser un
gestor de Django: ya no tiene ``.all``, así que el ``in="docs.order_line.all"``
que ``0002`` sembró no resuelve. Esta migración corrige la fila ya sembrada;
la constante de ``data/report_templates.py`` ya trae la forma nueva para las
bases que se siembren después (``designs/sale-basemodel-u3b-order.md``).

Escribe sobre el modelo histórico y sólo toca la fila de la clave del reporte
que todavía lleva la forma vieja; el reverse la restaura.
"""

from django.db import migrations

from addons.sale.data.report_templates import REPORT_SALEORDER_KEY

OLD = 'in="docs.order_line.all"'
NEW = 'in="docs.order_line"'


def _replace(apps, schema_editor, old, new):
    IrUiView = apps.get_model('base', 'IrUiView')
    alias = schema_editor.connection.alias
    views = IrUiView.objects.using(alias).filter(
        key=REPORT_SALEORDER_KEY, arch_db__contains=old
    )
    for view in views:
        view.arch_db = view.arch_db.replace(old, new)
        view.save(update_fields=['arch_db'])


def forward(apps, schema_editor):
    _replace(apps, schema_editor, OLD, NEW)


def backward(apps, schema_editor):
    _replace(apps, schema_editor, NEW, OLD)


class Migration(migrations.Migration):

    dependencies = [
        ('sale', '0019_restrict_ondelete_block_f'),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
