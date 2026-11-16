"""La seguridad de ``purchase`` y la aprobación en dos niveles que gobierna.

≙ ``odoo19c: addons/purchase/security/purchase_security.xml`` e
``ir.model.access.csv``, cargados por el manifiesto; y
``purchase_order.py:615-639,1251-1260`` (``button_approve``,
``button_confirm``, ``_approval_allowed``) con usuarios reales de esos
grupos. Las expectativas de datos se leen de los archivos de la fuente.
Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
purchase-security.md``.
"""
import csv
import pathlib
import xml.etree.ElementTree as ET
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from addons.base.models import IrModelData, ResCompany, ResPartner
from addons.base.models.ir_model import IrModelAccess
from addons.base.models.ir_rule import IrRule
import modules.loading as loading
from orm.environments import Environment, company_scope, sudo
from orm.utils import SUPERUSER_ID
from orm.registry import MODELS_BY_NAME
from tools.convert import convert_file
from tests.factories.product_factory import make_product

pytestmark = pytest.mark.django_db

SOURCE = pathlib.Path('/home/user/odoo-tools/19.x/odoo-19.0/odoo-19.0/'
                      'odoo-19.0/addons/purchase/security')
PORT = pathlib.Path(__file__).resolve().parents[3] / 'addons/purchase/security'
OMITTED_RULES = {'purchase_bill_union_comp_rule',
                 'purchase_order_report_comp_rule'}
MODES = ('read', 'write', 'create', 'unlink')

needs_source = pytest.mark.skipif(not SOURCE.is_dir(),
                                  reason='odoo-tools no montado')


@pytest.fixture(autouse=True)
def _installed(db):
    """Retira lo que ``purchase`` cargó al crear la base y vuelve a cargar:
    sin la retirada la prueba mediría la carga de entonces."""
    for model in (IrModelAccess, IrRule):
        rows = IrModelData.objects.filter(module='purchase',
                                          model=model._meta.label)
        model.objects.filter(
            pk__in=list(rows.values_list('res_id', flat=True))).delete()
        rows.delete()
    loading.load_modules('default')


def _ref(xmlid):
    return IrModelData.ref(xmlid)


def _qualified(xmlid):
    return xmlid if '.' in xmlid else 'purchase.' + xmlid


def _source_records(model):
    return [record for record in
            ET.parse(SOURCE / 'purchase_security.xml').iter('record')
            if record.get('model') == model]


@needs_source
def test_every_group_and_privilege_of_the_source_is_loaded():
    for model in ('res.groups', 'res.groups.privilege'):
        for record in _source_records(model):
            if record.get('id').startswith('base.'):
                continue
            name = record.find("field[@name='name']").text
            assert _ref(_qualified(record.get('id'))).name == name


def test_the_groups_hang_as_in_the_source():
    user = _ref('purchase.group_purchase_user')
    manager = _ref('purchase.group_purchase_manager')
    privilege = _ref('purchase.res_groups_privilege_purchase')
    assert _ref('base.group_user') in user.implied_ids.all()
    assert user in manager.implied_ids.all()
    assert user.privilege == privilege == manager.privilege
    assert privilege.category == _ref('base.module_category_supply_chain')


def test_installing_links_the_reminder_group_to_internal_users():
    """El registro de ``base.group_user`` vive en un bloque
    ``noupdate="1"``: la fuente lo escribe al instalar y lo salta al
    actualizar (``convert.py``: ``if self.noupdate and self.mode != 'init'``).
    En la base de pruebas ``purchase`` ya consta instalado, así que se carga
    el archivo en modo ``init``."""
    with Environment('default', SUPERUSER_ID, {}):
        convert_file('purchase', 'security/purchase_security.xml', {},
                     mode='init')
    assert _ref('purchase.group_send_reminder') in _ref(
        'base.group_user').implied_ids.all()


@needs_source
def test_every_rule_of_the_source_is_loaded_but_the_declared():
    for record in _source_records('ir.rule'):
        rid = record.get('id')
        if rid in OMITTED_RULES:
            assert not IrModelData.objects.filter(
                module='purchase', name=rid).exists()
            continue
        rule = _ref(_qualified(rid))
        assert isinstance(rule, IrRule)
        domain = record.find("field[@name='domain_force']").text
        assert rule.domain_force == domain


@needs_source
def test_every_access_row_of_the_port_matches_the_source():
    source = {row['id']: row for row in
              csv.DictReader(open(SOURCE / 'ir.model.access.csv'))}
    port = [row for row in csv.DictReader(open(PORT / 'ir.model.access.csv'))
            if row.get('id')]
    assert len(port) == 25
    for row in port:
        assert row == source[row['id']]
        access = _ref('purchase.' + row['id'])
        assert (access.perm_read, access.perm_write, access.perm_create,
                access.perm_unlink) == tuple(
            row['perm_' + mode] == '1' for mode in MODES)


def _user(login, *xmlids):
    user = get_user_model().objects.create_user(
        login=login, password=None, name=login)
    for xmlid in xmlids:
        user.group_ids.add(_ref(xmlid))
    return user


def _modes(model, user):
    return tuple(IrModelAccess.check(model, mode, raise_exception=False,
                                     user=user) for mode in MODES)


def test_an_internal_user_has_no_purchase_orders():
    user = _user('po-acl-internal', 'base.group_user')
    assert _modes('purchase.order', user) == (False, False, False, False)


def test_the_purchase_user_writes_purchase_orders():
    user = _user('po-acl-user', 'purchase.group_purchase_user')
    assert _modes('purchase.order', user) == (True, True, True, True)


def _two_step_order(threshold):
    with sudo():
        company = ResCompany.objects.create(
            name='Compras dos niveles %s' % threshold,
            po_double_validation='two_step',
            po_double_validation_amount=threshold)
        vendor = ResPartner.objects.create(name='Proveedor dos niveles')
        [order] = MODELS_BY_NAME['purchase.order'].create(
            [{'partner_id': vendor.pk, 'company_id': company.pk,
              'currency_id': company.currency_id}])
        MODELS_BY_NAME['purchase.order.line'].create([{
            'order_id': order.id, 'name': 'Insumo',
            'price_unit': Decimal('100.00'),
            'product_id': make_product(name='Insumo dos niveles',
                                       price=Decimal('100.00')).pk}])
    return order


def _as(user, order, method):
    """Ejecuta como ``user``, miembro de la empresa de la orden y con ella
    activada: las reglas ``purchase_order_comp_rule`` filtran por
    ``company_ids``."""
    company = order.company_id
    user.company_ids.add(company)
    with Environment('default', user.pk, {}), company_scope(company.pk):
        getattr(order, method)()
    return MODELS_BY_NAME['purchase.order'].objects.get(pk=order.pk).state


def test_the_purchase_user_confirms_under_the_threshold():
    user = _user('po-2s-under', 'purchase.group_purchase_user')
    assert _as(user, _two_step_order(5000), 'button_confirm') == 'purchase'


def test_the_purchase_user_leaves_it_to_approve_over_the_threshold():
    user = _user('po-2s-over', 'purchase.group_purchase_user')
    assert _as(user, _two_step_order(50), 'button_confirm') == 'to approve'


def test_the_purchase_user_cannot_approve_it():
    user = _user('po-2s-noapprove', 'purchase.group_purchase_user')
    order = _two_step_order(50)
    _as(user, order, 'button_confirm')
    assert _as(user, order, 'button_approve') == 'to approve'


def test_the_purchase_manager_approves_it():
    user = _user('po-2s-user2', 'purchase.group_purchase_user')
    manager = _user('po-2s-manager', 'purchase.group_purchase_manager')
    order = _two_step_order(50)
    _as(user, order, 'button_confirm')
    assert _as(manager, order, 'button_approve') == 'purchase'


def test_the_manager_confirms_over_the_threshold_directly():
    manager = _user('po-2s-direct', 'purchase.group_purchase_manager')
    assert _as(manager, _two_step_order(50), 'button_confirm') == 'purchase'
