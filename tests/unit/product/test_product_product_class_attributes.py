"""La cabecera de ``product.product`` frente a la fuente.

≙ ``ProductProduct`` (``odoo19c: addons/product/models/product_product.py:
17-24, 121-124``). Con ``_name`` el modelo entra en ``MODELS_BY_NAME`` y
``env['product.product']`` resuelve —el respaldo de ``product_id`` en la
envoltura de base-lines—; con ``_inherits`` declarado, ``ensure_inherits``
cablea la delegación a la ficha con el mecanismo de ``orm/inherits.py``.
"""

import pytest
from django.db import connection

from addons.product.models import ProductProduct, ProductTemplate
from orm import models
from orm.environments import Environment
from orm.utils import SUPERUSER_ID

pytestmark = pytest.mark.unit


def test_the_class_attributes_the_source_declares():
    assert ProductProduct._name == 'product.product'
    assert ProductProduct._description == 'Product Variant'
    assert ProductProduct._inherits == {'product.template': 'product_tmpl_id'}
    assert ProductProduct._inherit == ['mail.thread', 'mail.activity.mixin']
    assert ProductProduct._order == 'default_code, name, id'
    assert (ProductProduct._check_company_domain.__func__
            is models.check_company_domain_parent_of)


def test_the_order_follows_the_template_name():
    """``name`` es de la ficha: ordenar por él es ordenar por la ficha."""
    assert ProductProduct._meta.ordering == [
        'default_code', 'product_tmpl__name', 'id']


@pytest.mark.django_db
def test_the_environment_resolves_the_model_by_its_name():
    with Environment(None, SUPERUSER_ID, {}) as env:
        assert env['product.product'] is ProductProduct


@pytest.mark.django_db
def test_the_delegation_is_wired_on_the_template_key():
    field = ProductProduct._meta.get_field('product_tmpl')
    assert getattr(field, 'delegate', False) is True
    # Lo que la ficha tiene y la variante no define, se delega.
    assert 'sequence' in ProductProduct._inherits_fields
    # Lo que la variante define por su cuenta gana: ``list_price`` es su
    # propiedad (precio de la ficha más el extra de atributos).
    assert 'list_price' not in ProductProduct._inherits_fields


@pytest.mark.django_db
def test_the_combination_index_is_on_the_table():
    """≙ ``_combination_unique = models.UniqueIndex('(product_tmpl_id,
    combination_indices) WHERE active IS TRUE')`` (``:121``)."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT indexdef FROM pg_indexes WHERE tablename = %s "
            "AND indexname = %s",
            ['product_product', 'product_product_combination_unique'])
        row = cursor.fetchone()
    assert row is not None
    assert 'UNIQUE' in row[0]
    assert 'active' in row[0]


def test_the_template_declares_its_class_attributes():
    """≙ ``ProductTemplate`` (``odoo19c: product_template.py:19-24, 180``):
    sin su ``_name`` ``ensure_inherits`` no encuentra el comodelo y la
    delegación de la variante no se cablea."""

    assert ProductTemplate._name == 'product.template'
    assert ProductTemplate._inherit == [
        'mail.thread', 'mail.activity.mixin', 'image.mixin']
    assert ProductTemplate._description == 'Product'
    assert ProductTemplate._order == 'is_favorite desc, name'
    assert ProductTemplate._check_company_auto is True
    assert (ProductTemplate._check_company_domain.__func__
            is models.check_company_domain_parent_of)


@pytest.mark.django_db
def test_the_template_favorite_index_is_on_the_table():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT indexdef FROM pg_indexes WHERE tablename = %s "
            "AND indexname = %s",
            ['product_template', 'product_template_is_favorite_index'])
        row = cursor.fetchone()
    assert row is not None
    assert 'is_favorite' in row[0]
