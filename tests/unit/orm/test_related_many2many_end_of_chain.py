"""Un ``related`` que termina en un ``Many2many`` de Django lee registros.

≙ ``value[self.related_field.name]`` de ``Field._compute_related``
(``odoo19c: odoo/orm/fields.py:696``): allá el último eslabón devuelve el
recordset de los registros relacionados. Sobre un modelo de Django ese
acceso da el gestor relacionado, que no se itera; el equivalente es su
``QuerySet``.
"""
import pytest
from django.db.models import Manager, QuerySet

from orm.fields import _end_of_chain
from tests.factories.product_factory import make_product

pytestmark = pytest.mark.django_db


def test_the_end_of_the_chain_reads_the_queryset_of_a_many2many():
    product = make_product(name='Variante related M2M')
    field = type(product)._meta.get_field('product_template_attribute_values')
    value = _end_of_chain(product, field)
    assert isinstance(value, QuerySet)
    assert not isinstance(value, Manager)
    assert list(value) == list(product.product_template_attribute_values.all())


def test_a_scalar_at_the_end_of_the_chain_is_read_as_is():
    product = make_product(name='Variante related escalar')
    field = type(product.product_tmpl)._meta.get_field('name')
    assert _end_of_chain(product.product_tmpl, field) == (
        product.product_tmpl.name)
