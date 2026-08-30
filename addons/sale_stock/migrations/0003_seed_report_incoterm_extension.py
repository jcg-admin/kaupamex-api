"""Siembra la extensión Incoterm sobre la plantilla del reporte de ``sale``.

El análogo nativo del template heredero de la referencia
(``report_saleorder_document_inherit_sale_stock``): al "instalar"
``sale_stock``, su parche XPath existe en BD y ``get_combined_arch`` de la
vista primaria lo aplica solo. Depende de la siembra de ``sale`` (la primaria
tiene que existir para colgar ``inherit_id``).

Idempotente por ``key``; el reverse borra sólo la fila de esta clave.
"""
from django.db import migrations

from addons.sale.data.report_templates import REPORT_SALEORDER_KEY
from addons.sale_stock.data.report_templates import (
    REPORT_INCOTERM_ARCH,
    REPORT_INCOTERM_KEY,
)


def seed_extension(apps, schema_editor):
    """Crea la vista de extensión colgada de la primaria de ``sale``."""
    IrUiView = apps.get_model('base', 'IrUiView')
    alias = schema_editor.connection.alias
    if IrUiView.objects.using(alias).filter(
            key=REPORT_INCOTERM_KEY).exists():
        return
    primary = IrUiView.objects.using(alias).filter(
        key=REPORT_SALEORDER_KEY, mode='primary').order_by(
        'priority', 'id').first()
    if primary is None:
        # silent OK because la primaria pudo des-sembrarse a mano (reverse de
        # sale.0002); una extensión sin ancla violaría el CHECK del modelo.
        return
    IrUiView.objects.using(alias).create(
        name='Incoterm en la orden de venta (sale_stock)',
        # El valor va CONGELADO: una migración escribe sobre el modelo
        # histórico, y el renombre a ``template`` lo aplica ``base/0070``
        # sobre las filas ya escritas.
        type='qweb', key=REPORT_INCOTERM_KEY,
        mode='extension', active=True,
        inherit_id=primary,
        arch_db=REPORT_INCOTERM_ARCH,
    )


def unseed_extension(apps, schema_editor):
    IrUiView = apps.get_model('base', 'IrUiView')
    alias = schema_editor.connection.alias
    IrUiView.objects.using(alias).filter(key=REPORT_INCOTERM_KEY).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('sale_stock', '0002_saleorderdelivery_incoterm_location'),
        ('sale', '0002_seed_report_saleorder_view'),
    ]

    operations = [
        migrations.RunPython(seed_extension, unseed_extension),
    ]
