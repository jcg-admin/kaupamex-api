"""Asignar el lado inverso de un ``Many2many`` es escribirlo.

≙ ``Field.__set__`` (``odoo19c: odoo/orm/fields.py:1807``): en la fuente
asignar un campo llama a ``write``. Aquí ``product_tag_ids`` es el accesor
inverso del ``Many2many`` que declara ``product.tag``
(``product_template_ids``), y ``product.template`` lo recibe con ese nombre.

*Métrica:* las filas de la relación tras asignar comandos, un valor falso y
la fila de Django sin pasar por ``write``.
*Ciega a:* el lado inverso de un registro sin guardar, que conserva la
conducta de Django.
"""
import pytest

from addons.product.models import ProductTag
from orm.commands import Command
from orm.environments import env, sudo

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _superuser():
    with sudo():
        yield


def _template():
    [template] = env()['product.template'].create([{
        'name': 'Inverso M2M'}])
    return template


def test_assigning_commands_writes_the_relation():
    template = _template()
    tag = ProductTag.objects.create(name='Etiqueta inversa')
    template.product_tag_ids = [Command.set([tag.pk])]
    assert template.product_tag_ids.ids == [tag.pk]


def test_assigning_false_clears_the_relation():
    template = _template()
    tag = ProductTag.objects.create(name='Etiqueta a vaciar')
    template.product_tag_ids = [Command.set([tag.pk])]
    template.product_tag_ids = False
    assert not template.product_tag_ids
