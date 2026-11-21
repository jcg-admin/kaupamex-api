"""La extensión de ``sale`` sobre ``product.pricelist.item`` en forma de
recordset.

≙ ``odoo19c: addons/sale/models/product_pricelist_item.py:7-15``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
product-pricelist-cluster.md``.

*Métrica:* ``_show_discount`` sobre el recordset vacío, sobre varios
registros, y sobre una regla de porcentaje con la funcionalidad encendida y
apagada.
*Ciega a:* la siembra real del grupo ``sale.group_discount_per_so_line``:
el interruptor se fija sustituyendo ``ResGroups._is_feature_enabled``.
"""
import pytest

from addons.base.models.res_groups import ResGroups
from addons.product.models.product_pricelist_item import (
    COMPUTE_FIXED, COMPUTE_PERCENTAGE)
from addons.sale.models.product_pricelist_item import (
    GROUP_DISCOUNT_PER_SO_LINE)
from orm.environments import env, sudo

pytestmark = pytest.mark.django_db

ITEM = 'product.pricelist.item'


@pytest.fixture(autouse=True)
def superuser():
    """Leer reglas exige el grupo de producto; la pregunta aquí es otra."""
    with sudo():
        yield


@pytest.fixture
def feature(monkeypatch):
    state = {'on': True}
    asked = []

    def is_enabled(group_reference):
        asked.append(group_reference)
        return state['on']

    monkeypatch.setattr(ResGroups, '_is_feature_enabled',
                        staticmethod(is_enabled))
    state['asked'] = asked
    return state


def _items(*compute_prices):
    return env()[ITEM].create(
        [{'compute_price': cp, 'pricelist_id': False}
         for cp in compute_prices])


def test_the_empty_recordset_shows_no_discount(feature):
    assert env()[ITEM].browse()._show_discount() is False
    assert feature['asked'] == []


def test_more_than_one_rule_is_an_error(feature):
    # Apagado, el ``and`` no llega a leer ``compute_price``: el error sólo
    # puede venir de ``ensure_one``.
    feature['on'] = False
    with pytest.raises(ValueError):
        _items(COMPUTE_PERCENTAGE, COMPUTE_PERCENTAGE)._show_discount()


def test_a_percentage_rule_follows_the_feature_switch(feature):
    item = _items(COMPUTE_PERCENTAGE)
    assert item._show_discount() is True
    assert feature['asked'] == [GROUP_DISCOUNT_PER_SO_LINE]
    feature['on'] = False
    assert item._show_discount() is False


def test_a_fixed_rule_never_shows_a_discount(feature):
    assert _items(COMPUTE_FIXED)._show_discount() is False
