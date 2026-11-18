"""``account_edi_proxy_client.user`` sobre ``BaseModel`` y con su ACL.

≙ ``odoo19c: addons/account_edi_proxy_client/models/``
``account_edi_proxy_user.py:25-33`` (el modelo es ``BaseModel``) y
``odoo19c: addons/account_edi_proxy_client/security/ir.model.access.csv``
(todo para ``base.group_system``; lectura para
``account.group_account_invoice``). Diseño: ``scripts/workbench/
orm-continuation-plan-20261103T095630/designs/
basemodel-adoption-account-edi-proxy-client.md``.
"""
import pytest
from django.contrib.auth import get_user_model

from addons.account_edi_proxy_client.models.account_edi_proxy_user import (
    AccountEdiProxyUser,
)
from addons.base.models import IrModelAccess, IrModelData
from exceptions import AccessError
from orm.environments import Environment, sudo, user_scope
from orm.models import BaseModel
from orm.registry import MODELS_BY_NAME

pytestmark = pytest.mark.django_db

MODEL = 'account_edi_proxy_client.user'


def _user(login, *xmlids):
    with sudo():
        user = get_user_model().objects.create_user(
            login=login, password=None, name=login)
    for xmlid in xmlids:
        module, name = xmlid.split('.')
        user.group_ids.add(MODELS_BY_NAME['res.groups'].objects.get(
            pk=IrModelData.objects.get(module=module, name=name).res_id))
    return user


def test_the_edi_proxy_user_is_a_base_model():
    assert issubclass(AccountEdiProxyUser, BaseModel)


def test_the_acl_is_the_reference_csv_with_its_external_ids():
    loaded = IrModelData.objects.filter(module='account_edi_proxy_client',
                                        model='base.IrModelAccess')
    rows = {name: IrModelAccess.objects.get(pk=loaded.get(name=name).res_id)
            for name in loaded.values_list('name', flat=True)}
    perms = {name: (row.perm_read, row.perm_write, row.perm_create,
                    row.perm_unlink) for name, row in rows.items()}
    assert perms == {
        'access_account_edi_proxy_manager': (True, True, True, True),
        'access_account_edi_proxy_user': (True, False, False, False),
    }


def test_an_internal_user_without_the_invoice_group_cannot_read():
    internal = _user('edi-proxy-internal', 'base.group_user')
    with user_scope(internal.pk), pytest.raises(AccessError):
        Environment(uid=internal.pk)[MODEL].search([])


def test_an_invoicing_user_reads_but_cannot_create():
    invoicing = _user('edi-proxy-invoicing', 'base.group_user',
                      'account.group_account_invoice')
    env = Environment(uid=invoicing.pk)
    with user_scope(invoicing.pk):
        assert not env[MODEL].search([])
        with pytest.raises(AccessError):
            env[MODEL].create({'id_client': 'x', 'proxy_type': 'peppol',
                               'edi_mode': 'test', 'edi_identification': 'y'})


def test_the_multi_company_rule_is_the_reference_one():
    """≙ ``account_edi_proxy_client_security.xml`` de la fuente."""
    rule = MODELS_BY_NAME['ir.rule'].objects.get(pk=IrModelData.objects.get(
        module='account_edi_proxy_client',
        name='account_edi_proxy_client_user_comp_rule').res_id)
    assert rule.domain_force == "[('company_id', 'parent_of', company_ids)]"
