"""Modelos del addon ``product_expiry`` — caducidad de productos y lotes.

Adaptación de Odoo ``product_expiry`` (``odoo-tools@622ddc2a``, ``odoo19c:``,
LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Este addon **no declara modelos propios**, y ésa es la corrección de forma de
:ref:`h-api-576`: como la referencia, extiende los que ya existen
(``product.template``, ``stock.lot``, ``stock.quant``, ``stock.move``). Cada
archivo espeja el nombre del suyo en la referencia y expone
``apply_product_expiry_extensions()``, que ``ProductExpiryConfig.ready()``
invoca — el idioma de extensión cross-app ya establecido en este árbol
(``account``, ``account_fleet``, ``l10n_mx``, ``account_qr_code_*``).
"""
