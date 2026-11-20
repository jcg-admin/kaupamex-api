"""Calculados y related sin columna sobre registros de ``new()``.

≙ ``Field.__get__`` (``odoo19c: odoo/orm/fields.py:1642-1806``),
``compute_value`` (``:1897-1918``), ``Field.write`` (``:1501-1518``) y
``_filter_not_equal`` (``:1577-1586``): sobre un registro nuevo sin origen,
un campo calculado se calcula, su resultado se escribe en la caché bajo
protección con el ``NewId`` como clave, y una relación vacía se lee como el
valor nulo del campo. Diseño: ``scripts/workbench/
orm-continuation-plan-20261103T095630/designs/newid-nonstored-compute.md``.
"""
import pytest
from django.db import connection
from django.db.models import QuerySet
from django.test.utils import CaptureQueriesContext

from addons.base.models import ResPartner
from addons.product.models import (
    ProductAttribute,
    ProductAttributeValue,
    ProductTemplateAttributeLine,
    ProductTemplateAttributeValue,
)
from orm.environments import env, sudo
from orm.identifiers import NewId
from tests.factories.product_factory import make_product

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _as_superuser():
    with sudo():
        yield


@pytest.fixture
def foo():
    bars = env()['test_orm.related_bar'].create(
        [{'name': 'Bar uno'}, {'name': 'Bar dos'}])
    [foo] = env()['test_orm.related_foo'].create(
        [{'name': 'Foo', 'bar_id': bars[0].id}])
    foo.bar_ids = bars
    return foo


def test_a_nonstored_related_reads_the_linked_value(foo):
    record = env()['test_orm.related'].new({'foo_id': foo.id})
    assert record.foo_name == 'Foo'
    assert record.foo_bar_name == 'Bar uno'


def test_a_nonstored_related_over_an_empty_link_reads_false():
    record = env()['test_orm.multi'].new({})
    assert record.name is False


def test_a_related_many2many_reads_all_the_records(foo):
    record = env()['test_orm.related'].new({'foo_id': foo.id})
    assert set(record.foo_bar_ids.mapped('name')) == {'Bar uno', 'Bar dos'}


def test_a_related_many2many_over_an_empty_link_is_empty():
    record = env()['test_orm.related'].new({})
    assert len(record.foo_bar_ids) == 0
    assert not record.foo_bar_ids


def test_a_nonstored_compute_on_a_new_record():
    """``root_categ`` es un calculado sin columna que depende de una
    relación (``@depends('parent')``)."""
    [root] = env()['test_orm.category'].create([{'name': 'Raíz'}])
    [child] = env()['test_orm.category'].create(
        [{'name': 'Hija', 'parent': root.id}])
    record = env()['test_orm.category'].new(
        {'name': 'Nieta', 'parent': child.id})
    assert record.root_categ == root


def test_changing_a_dependency_before_saving_recomputes(foo):
    [other] = env()['test_orm.related_foo'].create([{'name': 'Otro'}])
    record = env()['test_orm.related'].new({'foo_id': foo.id})
    assert record.foo_name == 'Foo'
    record.foo_id = other
    assert record.foo_name == 'Otro'


def test_sudo_and_with_env_keep_the_virtual_record(foo):
    record = env()['test_orm.related'].new({'foo_id': foo.id})
    assert record.sudo().foo_name == 'Foo'
    assert record.with_env(env()).foo_name == 'Foo'


def test_reading_keeps_the_identity_and_writes_no_sql(foo):
    record = env()['test_orm.related'].new({'foo_id': foo.id})
    [record_id] = record._ids
    with CaptureQueriesContext(connection) as queries:
        record.foo_name
        record.foo_bar_name
    writes = [q['sql'] for q in queries.captured_queries
              if q['sql'].lstrip().upper().startswith(
                  ('INSERT', 'UPDATE', 'DELETE'))]
    assert writes == []
    assert record._ids == (record_id,)
    assert isinstance(record_id, NewId)
    field = type(record)._fields['foo_name']
    assert field._get_cache(env())[record_id] == 'Foo'


def test_a_required_link_left_empty_reads_the_null_value():
    """``order_id`` es ``null=False``; sin asignar, la lectura no falla."""
    line = env()['purchase.order.line'].new({})
    assert not line.order_id
    assert line.state is False
    assert line.date_order is False
    assert not line.parent_id


def test_a_persisted_row_keeps_the_django_error():
    """La lectura vacía es sólo del registro virtual."""
    model = env()['purchase.order.line']
    row = type(model)()
    with pytest.raises(type(row).order_id.RelatedObjectDoesNotExist):
        row.order_id


def test_a_related_ending_on_a_django_many2many():
    attribute = ProductAttribute.objects.create(name='Color NewId')
    red = ProductAttributeValue.objects.create(attribute_id=attribute,
                                               name='Rojo')
    blue = ProductAttributeValue.objects.create(attribute_id=attribute,
                                                name='Azul')
    variant = make_product(name='Camiseta NewId')
    line = ProductTemplateAttributeLine.objects.create(
        product_tmpl=variant.product_tmpl, attribute_id=attribute)
    line.value_ids.set([red, blue])
    values = [ProductTemplateAttributeValue.objects.create(
        line=line, attribute_value=value) for value in (red, blue)]
    variant.product_template_attribute_values.set(values)
    record = env()['purchase.order.line'].new({'product_id': variant.pk})
    read = record.product_template_attribute_value_ids
    assert isinstance(read, QuerySet)
    assert set(read) == set(values)
    empty = env()['purchase.order.line'].new({})
    assert list(empty.product_template_attribute_value_ids) == []


def test_the_reported_consumers_read_on_new_records():
    partner = ResPartner.objects.create(name='Socio NewId')
    assert env()['test_orm.multi'].new(
        {'partner': partner.pk}).name == 'Socio NewId'
    assert env()['purchase.order'].new({}).lock_confirmed_po is False


def test_the_cache_key_guard_drops_only_the_unsaved_django_row(foo):
    """``_filter_not_equal_ids`` descarta el ``pk`` ``None`` y sólo a él.

    Con ``None`` como clave, el valor de una fila sin guardar le contestaría
    a la siguiente fila en vuelo; un ``NewId``, en cambio, es una clave de
    caché de la fuente (``odoo19c: odoo/orm/fields.py:1577-1586``).
    """
    model = env()['test_orm.related']
    field = type(model)._fields['name']
    unsaved = type(model)(name='Sin guardar')
    assert unsaved.pk is None
    assert field._filter_not_equal_ids([unsaved], 'Otro') == ()
    virtual = model.new({'name': 'Virtual'})
    assert field._filter_not_equal_ids(virtual, 'Otro') == virtual._ids
