"""``product.tag`` como ``BaseModel``, completo.

≙ ``odoo19c: addons/product/models/product_tag.py``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
product-tag-basemodel.md``.

*Métrica:* las variantes que la etiqueta reúne por sus dos vías, la búsqueda
sobre esa unión, la copia, la unicidad del nombre y el valor por defecto
leído del contexto.
*Ciega a:* el recorte de ``image`` a 200 píxeles, que no cambia aquí.
"""
import pytest
from django.db import IntegrityError, transaction

from addons.product.models import ProductTag
from orm.commands import Command
from orm.environments import env
from orm.models import BaseModel

pytestmark = pytest.mark.django_db

TAG = 'product.tag'


def _template(name):
    [template] = env()['product.template'].create([{'name': name}])
    return template


def _tag(**vals):
    values = dict({'name': 'PT Etiqueta'}, **vals)
    [tag] = env()[TAG].create([values])
    return tag


def test_the_tag_is_a_basemodel():
    assert issubclass(ProductTag, BaseModel)


def test_the_product_ids_join_both_paths():
    tagged = _template('PT Ficha etiquetada')
    loose = _template('PT Ficha suelta')
    tag = _tag(product_template_ids=[Command.set([tagged.id])],
               product_product_ids=[Command.set(
                   loose.product_variant_ids.ids)])
    expected = set(tagged.product_variant_ids.ids) | set(
        loose.product_variant_ids.ids)
    assert set(tag.product_ids.ids) == expected


def test_searching_the_product_ids_goes_through_both_paths():
    tagged = _template('PT Busca ficha')
    tag = _tag(name='PT Busca', product_template_ids=[
        Command.set([tagged.id])])
    found = env()[TAG].search(
        [('product_ids', 'in', tagged.product_variant_ids.ids)])
    assert tag.id in found.ids


def test_the_copy_marks_its_name():
    tag = _tag(name='PT Original')
    [vals] = tag.copy_data()
    assert vals['name'] == 'PT Original (copy)'


def test_the_name_is_unique():
    _tag(name='PT Única')
    with pytest.raises(IntegrityError), transaction.atomic():
        ProductTag.objects.create(name='PT Única')


def test_the_template_default_comes_from_the_context():
    template = _template('PT Contexto')
    [tag] = env()[TAG].with_context(product_template_id=template.id).create(
        [{'name': 'PT Nueva'}])
    assert tag.product_template_ids.ids == [template.id]
