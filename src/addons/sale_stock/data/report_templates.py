"""Extensión del reporte de la orden — el análogo del Incoterm de la referencia.

Espeja ``odoo19c: sale_stock/report/sale_order_report_templates.xml``
(``odoo-tools@622ddc2a``): un ``<template inherit_id="sale.report_saleorder_
document">`` inserta el bloque Incoterm con ``<xpath position="after">``. Aquí
la vista de extensión parcha la plantilla-descriptor de ``sale`` insertando su
campo en la sección ``notes`` — la superficie de extensión que el helper de
layout fijo dibuja línea a línea.

La condición ``{% if %}`` reproduce el ``t-if="doc.incoterm"`` de la fuente:
sin dato, el campo rinde vacío y el helper no dibuja la línea.
"""
from addons.base.models.ir_ui_view import IrUiView
from addons.sale.data.report_templates import REPORT_SALEORDER_KEY


#: ``key`` propia de la extensión — como el ``id`` del template heredero de la
#: referencia (``report_saleorder_document_inherit_sale_stock``).
REPORT_INCOTERM_KEY = 'sale_stock.report_saleorder_incoterm'

REPORT_INCOTERM_ARCH = """\
<xpath expr="//section[@name='notes']" position="inside">
  <field name="incoterm">{% if docs.delivery.incoterm_location %}Incoterm: {{ docs.delivery.incoterm_location }}{% endif %}</field>
</xpath>
"""


def seed(using=None):
    """Siembra la extensión Incoterm colgada de la primaria de ``sale``.

    Idempotente, mismo spec que ``sale_stock.0003``. Si la primaria no existe
    todavía, no hace nada: una extensión sin ancla violaría el CHECK del
    modelo. El orden queda garantizado por el catálogo de ``_SEEDERS``, que
    llama primero al de ``sale``.
    """
    manager = IrUiView.objects.using(using) if using else IrUiView.objects
    if manager.filter(key=REPORT_INCOTERM_KEY).exists():
        return
    primary = manager.filter(
        key=REPORT_SALEORDER_KEY, mode='primary').order_by(
        'priority', 'id').first()
    if primary is None:
        return
    manager.create(
        name='Incoterm en la orden de venta (sale_stock)',
        type='qweb', key=REPORT_INCOTERM_KEY,
        mode='extension', active=True, inherit_id=primary,
        arch_db=REPORT_INCOTERM_ARCH,
    )
