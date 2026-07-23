"""Modelos del addon ``product`` (base del monolito modular) — atributos reutilizables.

Adaptación de Odoo ``product.attribute*`` (verificado en 18 y 19): atributos
reutilizables entre productos, con valores por-producto (``price_extra``) y la
generación cartesiana de combinaciones. Enriquece el ``chartsize`` original
(variantes de un solo eje por producto) hacia el modelo multi-atributo de Odoo.
"""
from addons.product.models.product_attribute import ProductAttribute
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
    'ProductAttributeValue',
    'ProductTemplateAttributeLine',
    'ProductTemplateAttributeValue',
]
