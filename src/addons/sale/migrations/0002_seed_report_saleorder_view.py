"""Siembra la plantilla del reporte de la orden como fila de ``ir.ui.view``.

Es el aterrizaje nativo del ``data/*.xml`` de la referencia: al "instalar"
``sale``, su plantilla QWeb existe en BD y ``_descriptor_from_view`` la
resuelve por ``key``. Patrón H-API-263 — el spec vive en ``data/`` (una
constante) y la migración escribe sobre el modelo **histórico**.

Idempotente y ``noupdate``: nunca pisa una fila que ya exista con la clave.
"""
from django.db import migrations

from addons.sale.data.report_templates import (
    REPORT_SALEORDER_ARCH,
    REPORT_SALEORDER_KEY,
)


def seed_view(apps, schema_editor):
    """Crea la vista primaria del reporte si la clave no existe.

    Escribe sobre el modelo **histórico** (``apps.get_model``), no sobre
    ``data.seed()``: una migración no debe importar el modelo vivo. El spec
    —``ARCH`` y ``KEY``— sí es el mismo que consume ``seed()``, así que no hay
    dos copias que puedan divergir.
    """
    IrUiView = apps.get_model('base', 'IrUiView')
    alias = schema_editor.connection.alias
    if not IrUiView.objects.using(alias).filter(
            key=REPORT_SALEORDER_KEY).exists():
        IrUiView.objects.using(alias).create(
            name='Orden de venta (plantilla del documento)',
            type='qweb', key=REPORT_SALEORDER_KEY,
            mode='primary', active=True,
            arch_db=REPORT_SALEORDER_ARCH,
        )


def unseed_view(apps, schema_editor):
    """El reverse borra sólo la fila sembrada con esta clave y sin herederas."""
    IrUiView = apps.get_model('base', 'IrUiView')
    alias = schema_editor.connection.alias
    IrUiView.objects.using(alias).filter(
        key=REPORT_SALEORDER_KEY, inherit_id__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('sale', '0001_initial'),
        ('base', '0006_report_type_solo_pdf'),
    ]

    operations = [
        migrations.RunPython(seed_view, unseed_view),
    ]
