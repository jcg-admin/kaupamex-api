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
- ``product_product.py`` → ``ProductProduct``, la variante — lo que apunta un
  movimiento de stock o una línea de pedido. FK real a la ficha, **no**
  herencia multi-tabla: ésta admitiría una sola variante por ficha.
- ``product_pricelist.py`` → ``ProductPricelist``, el contenedor con su moneda
  y su alcance.
- ``product_pricelist_item.py`` → ``ProductPricelistItem``, la regla y el
  cálculo entero: los cinco pasos de la fórmula en el orden de la fuente.
- ``product_tag.py`` → ``ProductTag``, con sus **dos** M2M (ficha y variante
  suelta), que no son redundantes.
- ``product_uom.py`` → ``ProductUom``, el código de barras de un empaquetado;
  cierra la unicidad cruzada que ``product_product`` dejó anotada.
- ``product_supplierinfo.py`` → ``ProductSupplierinfo``, la tarifa de compra:
  precio, unidad y plazo por proveedor, con el alcance plantilla-o-variante.

Pendientes — **12** de los 25:
``product_combo{,_item}.py``, ``product_document.py``,
``product_catalog_mixin.py``, ``product_attribute_custom_value.py``,
``product_template_attribute_exclusion.py`` y las siete extensiones de
modelos de ``base`` (``res_company``, ``res_partner``, ``res_currency``,
``res_config_settings``, ``res_country_group``, ``ir_attachment``,
``uom_uom``).

La lista de pendientes de arriba nombraba ``product_pricelist{,_item}``,
``product_tag`` y ``product_uom`` **después** de que sus archivos aterrizaran:
es el defecto de cita rancia que H-API-149 fijó como barrido obligatorio, y
un índice es justo donde más engaña. Se corrige al registrar la tarifa.
"""
from addons.product.models.product_attribute import ProductAttribute
from addons.product.models.product_category import ProductCategory
from addons.product.models.product_pricelist import ProductPricelist
from addons.product.models.product_pricelist_item import (
    ProductPricelistItem,
)
from addons.product.models.product_product import ProductProduct
from addons.product.models.product_supplierinfo import ProductSupplierinfo
from addons.product.models.product_tag import ProductTag
from addons.product.models.product_uom import ProductUom
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
    'ProductPricelist',
    'ProductPricelistItem',
    'ProductProduct',
    'ProductSupplierinfo',
    'ProductTag',
    'ProductUom',
    'ProductTemplate',
    'ProductAttributeValue',
    'ProductTemplateAttributeLine',
    'ProductTemplateAttributeValue',
]
