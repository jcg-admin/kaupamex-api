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


pytestmark = [pytest.mark.integration, pytest.mark.django_db]


@pytest.fixture
def variant():
    template = ProductTemplate.objects.create(name='Camiseta')
    return ProductProduct.objects.create(product_tmpl=template, default_code='SKU')


@pytest.fixture
def values(variant):
    attribute = ProductAttribute.objects.create(name='Color')
    red = ProductAttributeValue.objects.create(attribute=attribute, name='Rojo')
    blue = ProductAttributeValue.objects.create(attribute=attribute, name='Azul')
    line = ProductTemplateAttributeLine.objects.create(
        product_tmpl=variant.product_tmpl, attribute=attribute,
    )
    line.values.set([red, blue])
    red_value = ProductTemplateAttributeValue.objects.create(line=line, attribute_value=red)
    blue_value = ProductTemplateAttributeValue.objects.create(line=line, attribute_value=blue)
    variant.product_template_attribute_values.add(red_value)
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
        template = variant.product_tmpl
        template.name = 'Playera'
        template.save(update_fields=['name'])
        assert variant.display_name == 'Playera'


def test_relation_change_invalidates_variant_label(variant, values):
    _, _, blue_value = values
    with transaction_scope():
        assert variant.display_name == 'Camiseta (Rojo)'
        variant.product_template_attribute_values.add(blue_value)
        assert variant.display_name == 'Camiseta (Rojo, Azul)'
        variant.product_template_attribute_values.clear()
        assert variant.display_name == 'Camiseta'


def test_attribute_name_change_invalidates_variant_label(variant, values):
    red, _, _ = values
    with transaction_scope():
        assert variant.display_name == 'Camiseta (Rojo)'
        red.name = 'Granate'
        red.save(update_fields=['name'])
        assert variant.display_name == 'Camiseta (Granate)'


def test_price_extra_change_invalidates_the_current_value_format(variant, values):
    _, red_value, _ = values
    with transaction_scope():
        assert variant.display_name == 'Camiseta (Rojo)'
        red_value.price_extra = Decimal('5.00')
        red_value.save(update_fields=['price_extra'])
        assert variant.display_name == 'Camiseta (Rojo (+5.00))'


def test_reverse_add_invalidates_the_owning_variant(variant, values):
    _, _, blue_value = values
    with transaction_scope():
        assert variant.display_name == 'Camiseta (Rojo)'
        blue_value.product_variant_ids.add(variant)
        assert variant.display_name == 'Camiseta (Rojo, Azul)'


def test_reverse_remove_and_clear_invalidate_previous_owners(variant, values):
    _, red_value, _ = values
    other = ProductProduct.objects.create(product_tmpl=variant.product_tmpl)
    other.product_template_attribute_values.add(red_value)
    with transaction_scope():
        assert variant.display_name == other.display_name == 'Camiseta (Rojo)'
        red_value.product_variant_ids.remove(variant)
        assert variant.display_name == 'Camiseta'
        assert other.display_name == 'Camiseta (Rojo)'
        red_value.product_variant_ids.clear()
        assert other.display_name == 'Camiseta'


def test_set_replacement_invalidates_the_previous_combination(variant, values):
    _, _, blue_value = values
    with transaction_scope():
        assert variant.display_name == 'Camiseta (Rojo)'
        variant.product_template_attribute_values.set([blue_value])
        assert variant.display_name == 'Camiseta (Azul)'


def test_unrelated_cached_variant_is_not_recomputed(variant, values, monkeypatch):
    _, _, blue_value = values
    other = ProductProduct.objects.create(product_tmpl=variant.product_tmpl)
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
        variant.product_template_attribute_values.add(blue_value)
        assert other.display_name == 'Camiseta'
        assert other.pk not in computed


def test_return_only_product_compute_remains_an_error(variant, monkeypatch):
    monkeypatch.setattr(ProductProduct, '_compute_display_name', lambda record: 'retorno')
    with transaction_scope(), pytest.raises(ValueError, match='failed to assign'):
        variant.display_name


def test_product_compute_failure_propagates(variant, monkeypatch):
    def fail(record):
        raise RuntimeError('fallo del producto')

    monkeypatch.setattr(ProductProduct, '_compute_display_name', fail)
    with transaction_scope(), pytest.raises(RuntimeError, match='fallo del producto'):
        variant.display_name
