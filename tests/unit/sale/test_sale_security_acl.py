"""La ACL de ``sale.order`` y ``sale.order.line``, cargada del manifiesto.

≙ ``odoo19c: addons/sale/security/ir.model.access.csv:28-39``.
Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
sale-security-acl.md``.

*Métrica:* las filas de ``ir.model.access`` que una instalación nueva crea
para cada modelo, con su grupo y sus cuatro permisos.
*Ciega a:* su efecto, que aparece al adoptar ``BaseModel`` (U3a/U3b), y a
las reglas de fila de ``addons/sale/security/ir_rules.py``.
"""
from types import SimpleNamespace

import pytest
from django.db import DEFAULT_DB_ALIAS

from addons.base.models import IrModelAccess
from modules.loading import load_data
from modules.module import get_manifest
from orm.environments import env, sudo

pytestmark = pytest.mark.django_db

ORDER_ROWS = {
    ('base.group_portal', (True, False, False, False)),
    ('account.group_account_readonly', (True, False, False, False)),
    ('account.group_account_invoice', (True, True, False, False)),
    ('account.group_account_user', (True, True, False, False)),
    ('sales_team.group_sale_salesman', (True, True, True, False)),
    ('sales_team.group_sale_manager', (True, True, True, True)),
}
LINE_ROWS = {
    ('base.group_portal', (True, False, False, False)),
    ('account.group_account_readonly', (True, False, False, False)),
    ('account.group_account_invoice', (True, True, False, False)),
    ('account.group_account_user', (True, True, False, False)),
    ('sales_team.group_sale_salesman', (True, True, True, True)),
}


def _installed_rows(model_xml_id):
    """Borra las filas que dejó una carga anterior, instala ``sale`` como
    una instalación nueva y devuelve las filas del modelo como
    ``(xml_id del grupo, permisos)``."""
    with sudo():
        model = env().ref(model_xml_id)
        IrModelAccess.objects.filter(model_id_id=model.pk).delete()
        package = SimpleNamespace(name='sale', manifest=get_manifest('sale'))
        load_data({}, 'init', 'data', package, using=DEFAULT_DB_ALIAS)
        by_pk = {}
        for xml_id in {group for group, _ in ORDER_ROWS | LINE_ROWS}:
            by_pk[env().ref(xml_id).pk] = xml_id
        return {
            (by_pk.get(row.group_id_id, row.group_id_id),
             (row.perm_read, row.perm_write, row.perm_create,
              row.perm_unlink))
            for row in IrModelAccess.objects.filter(model_id_id=model.pk)
        }


def test_sale_order_gets_the_source_acl():
    assert _installed_rows('sale.model_sale_order') == ORDER_ROWS


def test_sale_order_line_gets_the_source_acl():
    assert _installed_rows('sale.model_sale_order_line') == LINE_ROWS
