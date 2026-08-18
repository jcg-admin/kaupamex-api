"""Modelos de ``website_sale`` — espejo de ``addons/website_sale/models/``.

La referencia declara aquí **26 archivos**, casi todos extensiones de modelos
que pertenecen a otros addons (``product_template.py``, ``product_product.py``,
``delivery_carrier.py``, ``account_move.py``…). Ése es exactamente su papel:
``website_sale`` es el **puente** entre la tienda y el ERP, así que su carpeta
de modelos está llena de extensiones, no de modelos propios.

Portados por ahora — **3 de 26**:

``product_template.py``
    Publica el producto en la tienda.
``website.py``
    La política de recuperación de carrito del sitio (tarea **#258**).
``sale_order.py``
    El carrito abandonado y su recuperación (tarea **#258**).

Los dos últimos declaran modelos con tabla, así que se **importan** aquí: es
lo que hace que Django los registre. ``product_template.py`` no declara
ninguno —sólo cuelga un mixin— y por eso no aparece; su cableado vive donde
corresponde, en ``WebsiteSaleConfig.ready()``.

Las demás llegan con su superficie.
"""
from .sale_order import WebsiteSaleOrderInfo
from .website import WebsiteSaleSettings

__all__ = ['WebsiteSaleOrderInfo', 'WebsiteSaleSettings']
