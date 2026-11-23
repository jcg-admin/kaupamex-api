"""``account_edi`` sobre ``BaseModel``, con la ACL de la referencia.

≙ ``odoo19c: addons/account_edi/models/account_edi_format.py``
(``account.edi.format``), ``odoo19c:
addons/account_edi/models/account_edi_document.py`` (``account.edi.document``)
y ``odoo19c: addons/account_edi/security/ir.model.access.csv``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
basemodel-adoption-account-edi.md``.

*Métrica:* el tipo de cada modelo y las filas cargadas con el identificador
externo del módulo.
*Ciega a:* las vistas y el cron del manifiesto de la fuente.
"""
import pytest
from django.contrib.auth import get_user_model

import fields
from addons.account.models import AccountJournal
from addons.account_edi.models.account_edi_format import AccountEdiFormat
from addons.base.models import IrModelAccess, IrModelData, ResCompany
from exceptions import AccessError
from orm.environments import Environment, sudo, user_scope
from orm.models import BaseModel
from orm.registry import MODELS_BY_NAME

pytestmark = pytest.mark.django_db

MODELS = ('account.edi.format', 'account.edi.document')


@pytest.mark.parametrize('name', MODELS)
def test_each_model_is_a_base_model(name):
    assert issubclass(MODELS_BY_NAME[name], BaseModel)


def test_the_acl_is_the_reference_csv():
    xmlids = set(IrModelData.objects.filter(
        module='account_edi', model='ir.model.access',
    ).values_list('name', flat=True))
    assert xmlids == {
        'access_account_edi_format_readonly',
        'access_account_edi_format_group_invoice',
        'access_account_edi_document_readonly',
        'access_account_edi_document_group_invoice',
    }
    readonly = IrModelAccess.objects.get(pk=IrModelData.objects.get(
        module='account_edi',
        name='access_account_edi_document_readonly').res_id)
    assert (readonly.perm_read, readonly.perm_write, readonly.perm_create,
            readonly.perm_unlink) == (True, False, False, False)


def test_an_internal_user_reads_but_does_not_write_documents():
    group = MODELS_BY_NAME['res.groups'].objects.get(
        pk=IrModelData.objects.get(module='base', name='group_user').res_id)
    with sudo():
        user = get_user_model().objects.create_user(
            login='edi-acl-internal', password=None, name='interno')
    user.group_ids.add(group)
    with user_scope(user.pk):
        documents = Environment(uid=user.pk)['account.edi.document']
        documents.check_access('read')
        with pytest.raises(AccessError):
            documents.check_access('write')


class TestComputeEdiFormatIds:
    """≙ ``_compute_edi_format_ids`` (``odoo19c: account_edi/models/
    account_journal.py:54-79``), leído sobre el recordset del diario."""

    @pytest.fixture
    def journal(self):
        with sudo():
            company = ResCompany.objects.create(code='edi-c', name='EDI Co')
            return AccountJournal.objects.create(
                name='Ventas', code='SEDI', type='sale', company=company)

    @pytest.fixture
    def formats(self, monkeypatch):
        with sudo():
            default = AccountEdiFormat.objects.create(
                name='Por defecto', code='edi_default')
            manual = AccountEdiFormat.objects.create(
                name='Manual', code='edi_manual')
        monkeypatch.setattr(AccountEdiFormat, '_is_compatible_with_journal',
                            lambda self, journal: True)
        monkeypatch.setattr(
            AccountEdiFormat, '_is_enabled_by_default_on_journal',
            lambda self, journal: self.code == 'edi_default')
        return default, manual

    def test_a_default_format_is_enabled(self, journal, formats):
        default, _manual = formats
        with sudo():
            journal._compute_edi_format_ids()
            assert set(journal.edi_format_ids.ids) == {default.pk}

    def test_a_format_already_enabled_stays(self, journal, formats):
        default, manual = formats
        with sudo():
            journal.write({'edi_format_ids': [fields.Command.link(manual.pk)]})
            journal._compute_edi_format_ids()
            assert set(journal.edi_format_ids.ids) == {default.pk, manual.pk}
