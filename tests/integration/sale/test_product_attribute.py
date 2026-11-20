"""
Tests — addon ``product_attribute`` (atributos reutilizables + combinaciones).

Cubre el enriquecimiento del sistema de variantes hacia el modelo Odoo: un
atributo (Color, Talla) se define una vez y se reutiliza entre productos; cada
producto declara qué valores aplican, con su ``price_extra``; las combinaciones
son el producto cartesiano de los ejes y su precio = base + Σ price_extra.
"""

from decimal import Decimal

import pytest

from addons.product import services as pa_services
from addons.product.models import (
    ProductAttribute,
    ProductAttributeValue,
    ProductTemplateAttributeLine,
    ProductTemplateAttributeValue,
)
from tests.factories.product_factory import make_product

pytestmark = pytest.mark.integration

_slug_seq = [0]


def _product(price='100.00'):
    _slug_seq[0] += 1
    n = _slug_seq[0]
    return make_product(
        name=f'Attr {n}',
        default_code=f'ATR-{n:04d}',
        price=Decimal(price),
    )


def _attribute(name, values):
    attr = ProductAttribute.objects.create(name=name)
    objs = [
        ProductAttributeValue.objects.create(
            attribute_id=attr, name=v, sequence=i
        )
        for i, v in enumerate(values)
    ]
    return attr, objs


def _line(product, attr, values, sequence=10):
    line = ProductTemplateAttributeLine.objects.create(
        product_tmpl_id=product.product_tmpl_id,
        attribute_id=attr,
        sequence=sequence,
    )
    line.value_ids.set(values)
    return line


def test_attribute_is_reusable_across_products(db):
    color, (red, blue) = _attribute('Color', ['Rojo', 'Azul'])
    pa = _product()
    pb = _product()
    _line(pa, color, [red, blue])
    _line(pb, color, [red])
    # El mismo atributo Color se usa en dos productos distintos.
    assert color.template_lines.count() == 2
    assert red.template_lines.count() == 2


def test_sync_creates_template_values(db):
    color, (red, blue) = _attribute('Color', ['Rojo', 'Azul'])
    product = _product()
    line = _line(product, color, [red, blue])
    pa_services.sync_template_values(line)
    assert line.product_template_value_ids.count() == 2
    # Idempotente: no duplica.
    pa_services.sync_template_values(line)
    assert line.product_template_value_ids.count() == 2


def test_cartesian_combinations(db):
    color, colors = _attribute('Color', ['Rojo', 'Azul'])
    size, sizes = _attribute('Talla', ['S', 'M', 'L'])
    product = _product()
    _line(product, color, colors, sequence=1)
    _line(product, size, sizes, sequence=2)
    combos = pa_services.combinations(product.product_tmpl_id)
    # 2 colores × 3 tallas = 6 combinaciones.
    assert len(combos) == 6
    assert pa_services.combination_count(product.product_tmpl_id) == 6
    # Cada combinación tiene un PTAV por eje (2).
    assert all(len(c) == 2 for c in combos)


def test_combination_price_adds_price_extra(db):
    size, (s, m, l) = _attribute('Talla', ['S', 'M', 'L'])
    product = _product(price='100.00')
    line = _line(product, size, [s, m, l])
    pa_services.sync_template_values(line)
    # XL cuesta +50; S y M sin extra.
    ptav_l = ProductTemplateAttributeValue.objects.get(
        attribute_line_id=line, product_attribute_value_id=l
    )
    ptav_l.price_extra = Decimal('50.00')
    ptav_l.save(update_fields=['price_extra', 'write_date'])
    ptav_s = ProductTemplateAttributeValue.objects.get(
        attribute_line_id=line, product_attribute_value_id=s
    )
    # Precio de la combinación S = 100 ; combinación L = 150.
    assert pa_services.combination_price(
        product.product_tmpl_id, [ptav_s]
    ) == Decimal('100.00')
    assert pa_services.combination_price(
        product.product_tmpl_id, [ptav_l]
    ) == Decimal('150.00')


def test_multi_axis_price_sums_extras(db):
    color, (red, gold) = _attribute('Color', ['Rojo', 'Dorado'])
    size, (s, xl) = _attribute('Talla', ['S', 'XL'])
    product = _product(price='200.00')
    lc = _line(product, color, [red, gold], sequence=1)
    ls = _line(product, size, [s, xl], sequence=2)
    pa_services.sync_template_values(lc)
    pa_services.sync_template_values(ls)
    # Dorado +30 ; XL +40.
    ProductTemplateAttributeValue.objects.filter(
        attribute_line_id=lc, product_attribute_value_id=gold
    ).update(price_extra=Decimal('30.00'))
    ProductTemplateAttributeValue.objects.filter(
        attribute_line_id=ls, product_attribute_value_id=xl
    ).update(price_extra=Decimal('40.00'))
    gold_ptav = ProductTemplateAttributeValue.objects.get(
        attribute_line_id=lc, product_attribute_value_id=gold
    )
    xl_ptav = ProductTemplateAttributeValue.objects.get(
        attribute_line_id=ls, product_attribute_value_id=xl
    )
    # Combinación Dorado+XL = 200 + 30 + 40 = 270.
    assert pa_services.combination_price(
        product.product_tmpl_id, [gold_ptav, xl_ptav]
    ) == Decimal('270.00')


def test_no_lines_yields_single_empty_combination(db):
    product = _product()
    assert pa_services.combinations(product.product_tmpl_id) == [()]
    assert pa_services.combination_count(product.product_tmpl_id) == 0
    assert pa_services.combination_price(
        product.product_tmpl_id, ()
    ) == Decimal('100.00')
