"""Los datos de seguridad de ``account`` entran por su manifiesto.

≙ ``odoo19c: addons/account/__manifest__.py`` (clave ``data``):
``security/account_security.xml`` e ``ir.model.access.csv``. Las
expectativas se leen de los archivos de la fuente, no se copian aquí; las
omisiones son las que declara la cabecera del XML portado. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
account-security.md``.
"""
import csv
import pathlib
import xml.etree.ElementTree as ET

import pytest
from django.contrib.auth import get_user_model

from addons.base.models import IrModelData
from addons.base.models.ir_model import IrModelAccess
from addons.base.models.ir_rule import IrRule
import modules.loading as loading

pytestmark = pytest.mark.django_db

SOURCE = pathlib.Path('/home/user/odoo-tools/19.x/odoo-19.0/odoo-19.0/'
                      'odoo-19.0/addons/account/security')
PORT = pathlib.Path(__file__).resolve().parents[3] / 'addons/account/security'
OMITTED_RULES = {
    'account_analytic_line_rule_billing_user',
    'account_analytic_line_rule_readonly_user',
    'invoice_analysis_comp_rule',
    'account_move_send_single_rule_group_invoice',
    'account_move_send_batch_rule_group_invoice',
    'account_comp_rule',
}
MODES = ('read', 'write', 'create', 'unlink')

needs_source = pytest.mark.skipif(not SOURCE.is_dir(),
                                  reason='odoo-tools no montado')


@pytest.fixture(autouse=True)
def _installed(db):
    """Retira, dentro de la transacción de la prueba, los accesos y las
    reglas que ``account`` cargó al crear la base, y vuelve a ejecutar el
    ciclo. Sin la retirada la prueba mediría la carga de entonces: con el CSV
    fuera del manifest seguía en verde."""
    for model in (IrModelAccess, IrRule):
        label = model._meta.label
        rows = IrModelData.objects.filter(module='account', model=label)
        model.objects.filter(
            pk__in=list(rows.values_list('res_id', flat=True))).delete()
        rows.delete()
    loading.load_modules('default')


def _ref(xmlid):
    return IrModelData.ref(xmlid)


def _source_records(model):
    tree = ET.parse(SOURCE / 'account_security.xml')
    return [record for record in tree.iter('record')
            if record.get('model') == model]


def _qualified(xmlid):
    return xmlid if '.' in xmlid else 'account.' + xmlid


@needs_source
def test_every_group_and_privilege_of_the_source_is_loaded():
    for model in ('res.groups', 'res.groups.privilege'):
        for record in _source_records(model):
            if record.get('id').startswith('base.'):
                continue
            name = record.find("field[@name='name']").text
            assert _ref(_qualified(record.get('id'))).name == name


@needs_source
def test_the_groups_imply_what_the_source_implies():
    invoice = _ref('account.group_account_invoice')
    readonly = _ref('account.group_account_readonly')
    basic = _ref('account.group_account_basic')
    user = _ref('account.group_account_user')
    manager = _ref('account.group_account_manager')
    assert _ref('base.group_user') in invoice.implied_ids.all()
    assert invoice in basic.implied_ids.all()
    assert {basic, readonly} <= set(user.implied_ids.all())
    assert invoice in manager.implied_ids.all()
    privilege = _ref('account.res_groups_privilege_accounting')
    assert invoice.privilege == privilege == manager.privilege
    assert privilege.category == _ref('base.module_category_accounting')
    assert _ref('base.group_system') in _ref(
        'account.group_validate_bank_account').implied_by_ids.all()


@needs_source
def test_every_rule_of_the_source_is_loaded_but_the_declared():
    for record in _source_records('ir.rule'):
        rid = record.get('id')
        if rid in OMITTED_RULES:
            assert not IrModelData.objects.filter(
                module='account', name=rid).exists()
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
    assert len(port) == 99
    for row in port:
        assert row == source[row['id']]
        access = _ref('account.' + row['id'])
        assert isinstance(access, IrModelAccess)
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


def test_an_internal_user_without_billing_has_no_journal_entries():
    user = _user('acc-acl-internal', 'base.group_user')
    assert _modes('account.move', user) == (False, False, False, False)


def test_the_billing_user_writes_journal_entries():
    user = _user('acc-acl-invoice', 'account.group_account_invoice')
    assert _modes('account.move', user) == (True, True, True, True)


def test_the_readonly_user_only_reads_them():
    user = _user('acc-acl-readonly', 'account.group_account_readonly')
    assert _modes('account.move', user) == (True, False, False, False)


def test_account_names_the_partner_it_extends():
    """``_reflect_models`` da el xmlid del modelo a cada módulo que lo
    extiende; la fila de ``res.partner`` del CSV lo cita sin prefijo."""
    assert _ref('account.model_res_partner') == _ref('base.model_res_partner')
