"""Modelos del addon ``product`` — espejo de ``addons/product/models/``.

La referencia tiene **25** archivos además del ``__init__``. Portados hasta
ahora, con lo que aporta cada uno:

- ``product_attribute.py`` · ``product_attribute_value.py`` ·
  ``product_template_attribute_line.py`` · ``product_template_attribute_value.py``
  — atributos reutilizables entre productos, valores por-producto
  (``price_extra``) y la generación cartesiana de combinaciones.
- ``product_category.py`` → ``ProductCategory``, el árbol de categorías con su
  ruta materializada y su nombre completo repropagado.
- ``product_template.py`` → ``ProductTemplate``, el producto del catálogo:
  nombre, categoría, precio, unidad. FK **reales** a ``product.category`` y a
  ``uom.uom``, que ya están portados.

Pendientes, encabezados por ``product_product.py`` (1197) —la variante, que es
lo que apunta un movimiento de stock o una línea de pedido—, más
``product_pricelist{,_item}.py``, ``product_supplierinfo.py``,
``product_combo{,_item}.py``, ``product_tag.py``, ``product_document.py``,
``product_catalog_mixin.py``, ``product_uom.py``,
``product_attribute_custom_value.py``,
``product_template_attribute_exclusion.py`` y las siete extensiones de
modelos de ``base`` (``res_company``, ``res_partner``, ``res_currency``,
``res_config_settings``, ``res_country_group``, ``ir_attachment``,
``uom_uom``).
"""
from addons.product.models.product_attribute import ProductAttribute
from addons.product.models.product_category import ProductCategory
from addons.product.models.product_template import ProductTemplate
from addons.product.models.product_attribute_value import (
    ProductAttributeValue,
)
from addons.product.models.product_template_attribute_line import (
    ProductTemplateAttributeLine,
)
from addons.product.models.product_template_attribute_value import (
    ProductTemplateAttributeValue,
)

__all__ = [
    'ProductAttribute',
    'ProductCategory',
    'ProductTemplate',
    'ProductAttributeValue',
    'ProductTemplateAttributeLine',
    'ProductTemplateAttributeValue',
]
