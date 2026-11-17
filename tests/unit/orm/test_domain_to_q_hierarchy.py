"""``DomainCondition._to_q`` con operadores de jerarquía.

Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
domain-to-q-hierarchy.md``. En la fuente ``child_of``/``parent_of`` se
reescriben en el nivel ``FULL`` del optimizador
(``odoo19c: odoo/orm/domains.py:1707-1760``) antes de llegar a SQL; aquí
``_to_q`` es el compilador que usa ``ir.rule._get_failing``.
"""
import pytest
from django.apps import apps

from addons.base.models import ResCompany
from orm.domains import Domain
from orm.environments import sudo

pytestmark = pytest.mark.django_db

AccountJournal = apps.get_model('account', 'AccountJournal')


@pytest.fixture(autouse=True)
def _as_superuser():
    with sudo():
        yield


@pytest.fixture
def journals():
    one = ResCompany.objects.create(code='h-one', name='H One')
    two = ResCompany.objects.create(code='h-two', name='H Two')
    return one, (
        AccountJournal.objects.create(name='J1', code='HJ1', type='general',
                                      company=one),
        AccountJournal.objects.create(name='J2', code='HJ2', type='general',
                                      company=two),
    )


def test_parent_of_compiles_to_the_companies_of_the_hierarchy(journals):
    one, (first, second) = journals
    condition = Domain('company_id', 'parent_of', [one.pk])
    found = AccountJournal.objects.filter(
        pk__in=[first.pk, second.pk]).filter(
        condition._to_q(AccountJournal))
    assert [journal.pk for journal in found] == [first.pk]


def test_parent_of_an_empty_list_matches_nothing(journals):
    _one, (first, second) = journals
    condition = Domain('company_id', 'parent_of', [])
    found = AccountJournal.objects.filter(
        pk__in=[first.pk, second.pk]).filter(
        condition._to_q(AccountJournal))
    assert not found.exists()
