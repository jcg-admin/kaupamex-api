"""Servicio de combinaciones — addon ``product`` (base del monolito modular).

Adaptación fiel de la generación de variantes de Odoo
(``product/models/product_template.py::_get_possible_combinations`` /
``_create_variant_ids``, verificado en 18 y 19): el **producto cartesiano** de
un valor por cada línea de atributo del producto, y el precio de cada
combinación = precio base + Σ ``price_extra``. Es el enriquecimiento que el
``chartsize`` de un solo eje no cubría.
"""
import itertools
from decimal import Decimal

from addons.product.models.product_template_attribute_value import (
    ProductTemplateAttributeValue,
)


def sync_template_values(line):
    """Crea el ``ProductTemplateAttributeValue`` de cada valor de la línea.

    Réplica de ``_update_product_template_attribute_values`` de Odoo: por cada
    valor en ``line.values`` asegura un PTAV (con ``price_extra=0`` si es nuevo).
    """
    created = []
    for value in line.values.all():
        ptav, was_created = ProductTemplateAttributeValue.objects.get_or_create(
            line=line, attribute_value=value,
        )
        if was_created:
            created.append(ptav)
    return created


def combinations(product):
    """Producto cartesiano de un PTAV por cada línea de atributo (Odoo).

    Devuelve una lista de combinaciones; cada combinación es una tupla de
    ``ProductTemplateAttributeValue`` (uno por línea, en orden de ``sequence``).
    Sin líneas → una combinación vacía (el producto sin variantes).
    """
    lines = list(product.attribute_lines.order_by('sequence', 'id'))
    per_line = []
    for line in lines:
        ptavs = list(line.template_values.order_by('id'))
        if not ptavs:
            sync_template_values(line)
            ptavs = list(line.template_values.order_by('id'))
        if ptavs:
            per_line.append(ptavs)
    if not per_line:
        return [()]
    return [tuple(combo) for combo in itertools.product(*per_line)]


def combination_price(product, ptavs) -> Decimal:
    """Precio de una combinación = precio base + Σ ``price_extra``.

    Fiel a ``odoo19c: addons/product/models/product_template.py:720-727``, que
    suma los ``price_extra`` de los valores de atributo de la combinación al
    precio de la ficha.

    El campo de la ficha es ``list_price``, no ``price``: la referencia no
    declara ``price`` en ``product.template``. Leerlo lanzaba
    ``AttributeError`` en cualquier llamada real — el defecto sobrevivió
    porque no había test que ejercitara esta función. Ver H-API-217.
    """
    total = Decimal(product.list_price)
    for ptav in ptavs:
        total += ptav.price_extra
    return total.quantize(Decimal('0.01'))


def combination_count(product) -> int:
    """Número de combinaciones posibles (Odoo product_variant_count)."""
    count = 1
    has_line = False
    for line in product.attribute_lines.all():
        n = line.template_values.count() or line.values.count()
        if n:
            has_line = True
            count *= n
    return count if has_line else 0
