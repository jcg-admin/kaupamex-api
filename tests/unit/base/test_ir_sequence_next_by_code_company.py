"""``next_by_code`` con empresa ve también la secuencia global.

≙ ``odoo19c: odoo/addons/base/models/ir_sequence.py:287``:
``search([('code', '=', code), ('company_id', 'in', [company_id, False])],
order='company_id')``. La de la empresa gana; sin ella, la global.

Métrica: el texto que devuelve ``next_by_code``.
Ciega a: ``check_access``, que aquí vive en la vista.
"""
import pytest

from addons.base.models import IrSequence, ResCompany

pytestmark = pytest.mark.django_db

CODE = 'test.next_by_code.company'


@pytest.fixture
def company():
    return ResCompany.objects.create(name='Secuencias', code='seq-comp')


def _sequence(prefix, company=None):
    return IrSequence.objects.create(
        name=prefix, code=CODE, prefix=prefix, padding=3, company=company)


def test_the_global_sequence_serves_a_company(company):
    _sequence('GLOBAL')
    assert IrSequence.next_by_code(CODE, company=company) == 'GLOBAL001'


def test_the_company_sequence_wins_over_the_global(company):
    _sequence('GLOBAL')
    _sequence('OWN', company=company)
    assert IrSequence.next_by_code(CODE, company=company) == 'OWN001'


def test_another_company_sequence_is_not_used(company):
    other = ResCompany.objects.create(name='Otra', code='seq-other')
    _sequence('OTHER', company=other)
    assert IrSequence.next_by_code(CODE, company=company) is None
