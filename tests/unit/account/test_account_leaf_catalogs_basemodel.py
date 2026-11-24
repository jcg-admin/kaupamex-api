"""Los cuatro catálogos hoja de ``account`` sobre ``BaseModel``.

≙ ``odoo19c: addons/account/models/account_incoterms.py:7-9``,
``account_lock_exception.py:11-13``, ``account_cash_rounding.py:8-17`` y
``account_journal.py:16-35``: la identidad de cada clase y el recordset
que devuelve ``excluded_journal_ids``.
"""
import pytest

from addons.account.models import (
    AccountCashRounding, AccountIncoterms, AccountJournalGroup,
    AccountLockException)
from orm.models import BaseModel

pytestmark = pytest.mark.django_db

LEAVES = (AccountIncoterms, AccountLockException, AccountCashRounding,
          AccountJournalGroup)


@pytest.mark.parametrize('model', LEAVES, ids=lambda m: m._name)
def test_each_leaf_catalog_is_a_basemodel(model):
    assert issubclass(model, BaseModel)


def test_the_company_attributes_the_source_declares():
    assert AccountCashRounding._check_company_auto is True
    assert AccountJournalGroup._check_company_auto is True


def test_an_incoterm_is_a_recordset():
    incoterm = AccountIncoterms.objects.create(name='Ex Works', code='EXW')
    assert isinstance(incoterm, BaseModel)
    assert incoterm.browse(incoterm.ids).code == 'EXW'


def test_excluded_journals_of_a_group_is_a_recordset():
    group = AccountJournalGroup.objects.create(name='Libro U1')
    journals = group.excluded_journals
    assert isinstance(journals, BaseModel)
    assert not journals
    assert journals.ids == []
