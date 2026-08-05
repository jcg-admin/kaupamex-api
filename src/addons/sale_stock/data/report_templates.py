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

#: ``key`` propia de la extensión — como el ``id`` del template heredero de la
#: referencia (``report_saleorder_document_inherit_sale_stock``).
REPORT_INCOTERM_KEY = 'sale_stock.report_saleorder_incoterm'

REPORT_INCOTERM_ARCH = """\
<xpath expr="//section[@name='notes']" position="inside">
  <field name="incoterm">{% if docs.delivery.incoterm_location %}Incoterm: {{ docs.delivery.incoterm_location }}{% endif %}</field>
</xpath>
"""
