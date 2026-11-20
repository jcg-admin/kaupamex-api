"""Un ``related`` que termina en un ``Many2many`` de Django lee registros.

≙ ``value[self.related_field.name]`` de ``Field._compute_related``
(``odoo19c: odoo/orm/fields.py:696``): allá el último eslabón devuelve el
recordset de los registros relacionados. Sobre un modelo de Django ese
acceso da el gestor relacionado, que no se itera; el equivalente es su
``QuerySet``.
"""
import pytest
from django.db.models import Manager, QuerySet

from addons.base.models import IrModelData, ResGroups
from orm.fields import _end_of_chain
from tests.factories.product_factory import make_product

pytestmark = pytest.mark.django_db


def test_the_end_of_the_chain_reads_the_queryset_of_a_many2many():
    """``res.groups`` sigue siendo modelo de Django: su ``implied_ids`` es el
    gestor relacionado y el último eslabón lo lee como ``QuerySet``."""
    group = IrModelData.objects.get(module='base', name='group_user')
    record = ResGroups.objects.get(pk=group.res_id)
    field = ResGroups._meta.get_field('implied_ids')
    value = _end_of_chain(record, field)
    assert isinstance(value, QuerySet)
    assert not isinstance(value, Manager)
    assert list(value) == list(record.implied_ids.all())


def test_the_end_of_the_chain_reads_the_recordset_of_a_base_model():
    """Sobre un ``BaseModel`` el campo ya es el recordset, como en la
    fuente, y se devuelve tal cual."""
    product = make_product(name='Variante related M2M')
    field = type(product)._meta.get_field(
        'product_template_attribute_value_ids')
    value = _end_of_chain(product, field)
    assert value == product.product_template_attribute_value_ids


def test_a_scalar_at_the_end_of_the_chain_is_read_as_is():
    product = make_product(name='Variante related escalar')
    field = type(product.product_tmpl_id)._meta.get_field('name')
    assert _end_of_chain(product.product_tmpl_id, field) == (
        product.product_tmpl_id.name)
