"""Asignar el lado inverso de un ``Many2many`` es escribirlo.

≙ ``Field.__set__`` (``odoo19c: odoo/orm/fields.py:1807``): en la fuente
``record.combo_ids = False`` llama a ``write``; aquí ``combo_ids`` es el
accesor inverso del ``Many2many`` que declara ``product.combo``, y
``product.template`` lo recibe con ese nombre
(``odoo19c: addons/product/models/product_template.py:604-606``).

*Métrica:* las filas de la relación tras asignar comandos, un valor falso y
la fila de Django sin pasar por ``write``.
*Ciega a:* el lado inverso de un registro sin guardar, que conserva la
conducta de Django.
"""
import pytest

from addons.product.models import ProductCombo
from orm.commands import Command
from orm.environments import env, sudo

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _superuser():
    with sudo():
        yield


def _template():
    [template] = env()['product.template'].create([{
        'name': 'Inverso M2M', 'type': 'combo'}])
    return template


def test_assigning_commands_writes_the_relation():
    template = _template()
    combo = ProductCombo.objects.create(name='Combo inverso')
    template.combo_ids = [Command.set([combo.pk])]
    assert list(template.combo_ids.values_list('pk', flat=True)) == [combo.pk]


def test_assigning_false_clears_the_relation():
    template = _template()
    combo = ProductCombo.objects.create(name='Combo a vaciar')
    template.combo_ids = [Command.set([combo.pk])]
    template.combo_ids = False
    assert not template.combo_ids.exists()
