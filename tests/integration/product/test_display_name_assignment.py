"""El consumidor de producto cumple asignación e invalidación del ORM."""

from decimal import Decimal
from functools import wraps

import pytest

from addons.product.models import (
    ProductAttribute,
    ProductAttributeValue,
    ProductProduct,
    ProductTemplate,
    ProductTemplateAttributeLine,
    ProductTemplateAttributeValue,
)
from orm.environments import transaction_scope
from exceptions import UserError
from orm.commands import Command

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


@pytest.fixture
def variant():
    template = ProductTemplate.objects.create(name='Camiseta')
    return ProductProduct.objects.create(
        product_tmpl_id=template, default_code='SKU'
    )


@pytest.fixture
def values(variant):
    attribute = ProductAttribute.objects.create(name='Color')
    red = ProductAttributeValue.objects.create(
        attribute_id=attribute, name='Rojo'
    )
    blue = ProductAttributeValue.objects.create(
        attribute_id=attribute, name='Azul'
    )
    line = ProductTemplateAttributeLine.objects.create(
        product_tmpl_id=variant.product_tmpl_id,
        attribute_id=attribute,
    )
    line.write({'value_ids': [Command.set([red.id, blue.id])]})
    red_value = ProductTemplateAttributeValue.objects.create(
        attribute_line_id=line, product_attribute_value_id=red
    )
    blue_value = ProductTemplateAttributeValue.objects.create(
        attribute_line_id=line, product_attribute_value_id=blue
    )
    variant.write({
        'product_template_attribute_value_ids': [Command.link(red_value.id)],
    })
    return red, red_value, blue_value


def test_product_label_and_snapshot_keep_the_existing_format(variant):
    with transaction_scope():
        assert variant.display_name == 'Camiseta'
        assert variant.display_name == 'Camiseta'
        assert str(variant) == '[SKU] Camiseta'


def test_product_compute_preserves_direct_return_and_assigns(variant):
    with transaction_scope():
        assert variant._compute_display_name() == 'Camiseta'
        assert variant.__dict__['display_name'] == 'Camiseta'


def test_template_name_change_invalidates_variant_label(variant):
    with transaction_scope():
        assert variant.display_name == 'Camiseta'
        template = variant.product_tmpl_id
        template.name = 'Playera'
        template.save(update_fields=['name'])
        assert variant.display_name == 'Playera'


def test_relation_change_invalidates_variant_label(variant, values):
    _, _, blue_value = values
    with transaction_scope():
        assert variant.display_name == 'Camiseta (Rojo)'
        variant.write({
            'product_template_attribute_value_ids': [
                Command.link(blue_value.id),
            ],
        })
        assert variant.display_name == 'Camiseta (Rojo, Azul)'
        variant.write({
            'product_template_attribute_value_ids': [Command.clear()],
        })
        assert variant.display_name == 'Camiseta'


def test_attribute_name_change_invalidates_variant_label(variant, values):
    red, _, _ = values
    with transaction_scope():
        assert variant.display_name == 'Camiseta (Rojo)'
        red.name = 'Granate'
        red.save(update_fields=['name'])
        assert variant.display_name == 'Camiseta (Granate)'


def test_price_extra_change_invalidates_the_current_value_format(
    variant, values
):
    _, red_value, _ = values
    with transaction_scope():
        assert variant.display_name == 'Camiseta (Rojo)'
        red_value.price_extra = Decimal('5.00')
        red_value.save(update_fields=['price_extra'])
        assert variant.display_name == 'Camiseta (Rojo (+5.00))'


def _orm_write(record, vals):
    """``write`` del ORM, por debajo de la guarda de PTAV.

    ``product.template.attribute.value`` rehúsa escribir
    ``ptav_product_variant_ids`` (``odoo19c:
    addons/product/models/product_template_attribute_value.py:81-96``); lo que
    estas pruebas miden es la invalidación del ORM al escribir el lado inverso
    de un ``Many2many``, que sigue existiendo debajo de esa guarda.
    """
    return super(ProductTemplateAttributeValue, record).write(vals)


def test_the_value_refuses_to_write_its_variants(variant, values):
    _, _, blue_value = values
    with pytest.raises(UserError):
        blue_value.write({
            'ptav_product_variant_ids': [Command.link(variant.id)],
        })


def test_reverse_add_invalidates_the_owning_variant(variant, values):
    _, _, blue_value = values
    with transaction_scope():
        assert variant.display_name == 'Camiseta (Rojo)'
        _orm_write(blue_value, {
            'ptav_product_variant_ids': [Command.link(variant.id)],
        })
        assert variant.display_name == 'Camiseta (Rojo, Azul)'


def test_reverse_remove_and_clear_invalidate_previous_owners(variant, values):
    _, red_value, _ = values
    # Inactiva: dos variantes ACTIVAS de una ficha con la misma combinación
    # las prohíbe ``_combination_unique`` (``odoo19c: product_product.py:121``,
    # ``WHERE active IS TRUE``); lo que se mide aquí no depende de ``active``.
    other = ProductProduct.objects.create(
        product_tmpl_id=variant.product_tmpl_id, active=False
    )
    other.write({
        'product_template_attribute_value_ids': [Command.link(red_value.id)],
    })
    with transaction_scope():
        assert variant.display_name == other.display_name == 'Camiseta (Rojo)'
        _orm_write(
            red_value,
            {'ptav_product_variant_ids': [Command.unlink(variant.id)]})
        assert variant.display_name == 'Camiseta'
        assert other.display_name == 'Camiseta (Rojo)'
        _orm_write(red_value, {'ptav_product_variant_ids': [Command.clear()]})
        assert other.display_name == 'Camiseta'


def test_set_replacement_invalidates_the_previous_combination(variant, values):
    _, _, blue_value = values
    with transaction_scope():
        assert variant.display_name == 'Camiseta (Rojo)'
        variant.write({
            'product_template_attribute_value_ids': [
                Command.set([blue_value.id]),
            ],
        })
        assert variant.display_name == 'Camiseta (Azul)'


def test_unrelated_cached_variant_is_not_recomputed(
    variant, values, monkeypatch
):
    _, _, blue_value = values
    # Inactiva: dos variantes ACTIVAS de una ficha con la misma combinación
    # las prohíbe ``_combination_unique`` (``odoo19c: product_product.py:121``,
    # ``WHERE active IS TRUE``); lo que se mide aquí no depende de ``active``.
    other = ProductProduct.objects.create(
        product_tmpl_id=variant.product_tmpl_id, active=False
    )
    original = ProductProduct._compute_display_name
    computed = []

    @wraps(original)
    def tracked(record):
        computed.append(record.pk)
        return original(record)

    monkeypatch.setattr(ProductProduct, '_compute_display_name', tracked)
    with transaction_scope():
        assert variant.display_name == 'Camiseta (Rojo)'
        assert other.display_name == 'Camiseta'
        computed.clear()
        variant.write({
            'product_template_attribute_value_ids': [
                Command.link(blue_value.id),
            ],
        })
        assert other.display_name == 'Camiseta'
        assert other.pk not in computed


def test_return_only_product_compute_remains_an_error(variant, monkeypatch):
    monkeypatch.setattr(
        ProductProduct, '_compute_display_name', lambda record: 'retorno'
    )
    with (
        transaction_scope(),
        pytest.raises(ValueError, match='failed to assign'),
    ):
        variant.display_name


def test_product_compute_failure_propagates(variant, monkeypatch):
    def fail(record):
        raise RuntimeError('fallo del producto')

    monkeypatch.setattr(ProductProduct, '_compute_display_name', fail)
    with (
        transaction_scope(),
        pytest.raises(RuntimeError, match='fallo del producto'),
    ):
        variant.display_name
