"""Plantilla del reporte de la orden de venta — la fila de ``ir.ui.view``.

Equivalente nativo de ``odoo19c: sale/report/sale_report_templates.xml``
(``odoo-tools@622ddc2a``): allá la plantilla QWeb del documento se declara en
un ``data/*.xml`` y aterriza en ``ir.ui.view`` al instalar el addon; aquí el
arch vive en esta constante y la data-migration del addon lo siembra (patrón
H-API-263: un consumidor de arranque sobre el modelo histórico).

**El arch espeja al builder** (``report/report_catalog.build_sale_order``):
mismo descriptor, campo por campo. El builder queda como respaldo
(Open/Closed del motor, ``base/models/ir_actions_report.py``); esta fila lo
releva como fuente y —la diferencia que importa— abre el documento a
extensiones XPath de otros addons sin tocar a ``sale``.

Notas de forma:

- Los importes van por ``|stringformat:'.2f'`` y no por ``floatformat``:
  ``stringformat`` es ``%``-formatting de Python, inmune a la localización
  (``floatformat`` con ``es-mx`` activo podría variar el separador).
- ``<section name="notes">`` es el **ancla de extensión**: vacía aquí, la
  parchan los addons (``sale_stock`` inserta su Incoterm — el análogo del
  ``<xpath>`` de ``sale_order_report_templates.xml`` de la referencia). El
  helper dibuja cada valor no vacío del objeto como una línea.
"""

#: ``key`` de la vista = ``report_name`` del reporte — la resolución de
#: ``_descriptor_from_view`` espeja ``_get_template_view`` de la referencia.
REPORT_SALEORDER_KEY = 'sale.report_saleorder'

REPORT_SALEORDER_ARCH = """\
<descriptor>
  <section name="issuer">
    <field name="name">{{ docs.company.name|default_if_none:'' }}</field>
    <field name="address">{{ docs.company.partner.contact_address }}</field>
    <field name="email">{{ docs.company.partner.email|default_if_none:'' }}</field>
    <field name="phone">{{ docs.company.partner.phone|default_if_none:'' }}</field>
    <field name="logo">{{ docs.company.logo_png_b64 }}</field>
  </section>
  <section name="buyer">
    <field name="name">{% if docs.partner.partner %}{{ docs.partner.partner.name|default_if_none:'' }}{% else %}{{ docs.guest_email|default_if_none:'' }}{% endif %}</field>
    <field name="address">{% if docs.partner.partner %}{{ docs.partner.partner.contact_address }}{% endif %}</field>
  </section>
  <field name="order_number">{% if docs.name %}{{ docs.name }}{% else %}#{{ docs.pk }}{% endif %}</field>
  <field name="date">{% if docs.date_order %}{{ docs.date_order|date:'c' }}{% else %}{{ docs.created_at|date:'c' }}{% endif %}</field>
  <field name="currency">{% if currency %}{{ currency }}{% else %}MXN{% endif %}</field>
  <list name="items" in="docs.order_line.all">
    <field name="name">{% if item.name %}{{ item.name }}{% else %}{{ item.product }}{% endif %}</field>
    <field name="sku">{{ item.product.default_code|default_if_none:'' }}</field>
    <field name="quantity">{{ item.product_uom_qty|stringformat:'s' }}</field>
    <field name="unit_price">{{ item.price_unit|stringformat:'.2f' }}</field>
    <field name="amount">{{ item.price_total|stringformat:'.2f' }}</field>
  </list>
  <section name="totals">
    <field name="subtotal">{{ docs.amount_untaxed|stringformat:'.2f' }}</field>
    <field name="tax">{{ docs.amount_tax|stringformat:'.2f' }}</field>
    <field name="total">{{ docs.amount_total|stringformat:'.2f' }}</field>
  </section>
  <section name="notes"></section>
</descriptor>
"""
