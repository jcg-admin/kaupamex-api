"""Modelos de ``website_sale`` — espejo de ``addons/website_sale/models/``.

La referencia declara aquí **26 archivos**, casi todos extensiones de modelos
que pertenecen a otros addons (``product_template.py``, ``product_product.py``,
``delivery_carrier.py``, ``account_move.py``…). Ése es exactamente su papel:
``website_sale`` es el **puente** entre la tienda y el ERP, así que su carpeta
de modelos está llena de extensiones, no de modelos propios.

Aquí se porta por ahora una sola: ``product_template.py``, que publica el
producto en la tienda. Las demás llegan con su superficie.
"""
