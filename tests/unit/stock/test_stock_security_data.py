"""Grupos, reglas y ACL de ``stock``, cargados del manifiesto.

≙ ``odoo19c: addons/stock/__manifest__.py:20-21``,
``odoo19c: addons/stock/security/stock_security.xml`` y
``odoo19c: addons/stock/security/ir.model.access.csv``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
stock-security-data.md``.

*Métrica:* las filas de ``res.groups``, ``ir.model.access`` e ``ir.rule``
que una instalación nueva de ``stock`` crea.
*Ciega a:* su efecto sobre modelos que aún no son ``BaseModel``.
"""
from types import SimpleNamespace

import pytest
from django.db import DEFAULT_DB_ALIAS

from addons.base.models import IrModelAccess, IrModelData, IrRule
from modules.loading import load_data
from modules.module import get_manifest
from orm.environments import env, sudo

pytestmark = pytest.mark.django_db

PICKING_ROWS = {
    ('stock.group_stock_user', (True, True, True, True)),
    ('stock.group_stock_manager', (True, True, True, True)),
}

#: Las reglas multiempresa de la fuente que este árbol carga, con su dominio.
RULES = {
    'stock.stock_picking_rule': "[('company_id', 'in', company_ids)]",
    'stock.stock_warehouse_comp_rule': "[('company_id', 'in', company_ids)]",
    'stock.stock_quant_rule':
        "[('company_id', 'in', company_ids + [False])]",
    'stock.stock_storage_category_rule':
        "[('company_id', 'in', company_ids + [False])]",
}


def _install_stock():
    package = SimpleNamespace(name='stock', manifest=get_manifest('stock'))
    load_data({}, 'init', 'data', package, using=DEFAULT_DB_ALIAS)


def test_the_stock_groups_exist_and_the_manager_implies_the_user():
    with sudo():
        # Las aristas se vacían antes de cargar: lo que se mide es la carga,
        # no las filas que la sesión ya hubiera sembrado.
        for xml_id in ('stock.group_stock_user', 'stock.group_stock_manager'):
            env().ref(xml_id).implied_ids.clear()
        _install_stock()
        user = env().ref('stock.group_stock_user')
        manager = env().ref('stock.group_stock_manager')
        assert user in manager.implied_ids.all()
        assert env().ref('base.group_user') in user.implied_ids.all()


def test_stock_picking_gets_the_source_acl():
    with sudo():
        model = env().ref('stock.model_stock_picking')
        IrModelAccess.objects.filter(model_id_id=model.pk).delete()
        _install_stock()
        by_pk = {env().ref(xml_id).pk: xml_id
                 for xml_id, _perms in PICKING_ROWS}
        rows = {
            (by_pk.get(row.group_id_id, row.group_id_id),
             (row.perm_read, row.perm_write, row.perm_create,
              row.perm_unlink))
            for row in IrModelAccess.objects.filter(model_id_id=model.pk)
        }
    assert rows == PICKING_ROWS


def test_the_multi_company_rules_are_loaded():
    with sudo():
        seeded = IrModelData.objects.filter(
            module='stock', name__in=[xml_id.split('.', 1)[1]
                                      for xml_id in RULES])
        IrRule.objects.filter(
            pk__in=list(seeded.values_list('res_id', flat=True))).delete()
        seeded.delete()
        _install_stock()
        for xml_id, domain in RULES.items():
            assert env().ref(xml_id).domain_force == domain
