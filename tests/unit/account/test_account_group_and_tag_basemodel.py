"""``account.group`` y ``account.account.tag`` sobre ``BaseModel``.

≙ ``odoo19c: addons/account/models/account_account.py:1497-1502`` y
``account_account_tag.py:7-9, 110-120``: la identidad, el árbol del grupo
como recordset y la guarda de borrado sobre el recordset.
"""
import pytest

from addons.account.models import AccountAccountTag, AccountGroup
from addons.base.models import ResCompany
from orm.models import BaseModel

pytestmark = pytest.mark.django_db


def test_the_group_declares_the_company_attributes():
    assert issubclass(AccountGroup, BaseModel)
    assert AccountGroup._check_company_auto is True


def test_the_children_of_a_group_are_a_recordset():
    company = ResCompany.objects.create(
        name='Kaupamex', code='kaupamex_test_account_u2')
    parent = AccountGroup.objects.create(
        name='Activo', code_prefix_start='1', code_prefix_end='1',
        company=company)
    child = AccountGroup.objects.create(
        name='Circulante', code_prefix_start='11', code_prefix_end='11',
        company=company)
    child = AccountGroup.objects.get(pk=child.pk)
    assert child.parent == parent
    assert child in parent.children


def test_a_tag_unlinks_through_the_recordset():
    tags = [AccountAccountTag.objects.create(name=name, applicability='taxes')
            for name in ('U2 a', 'U2 b')]
    recordset = tags[0].browse([tag.pk for tag in tags])
    recordset.unlink()
    assert not AccountAccountTag.objects.filter(
        name__in=['U2 a', 'U2 b']).exists()
