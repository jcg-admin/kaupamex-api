"""``account.payment.term`` y su línea sobre ``BaseModel``.

≙ ``odoo19c: addons/account/models/account_payment_term.py:11-15, 157-169,
281-284, 350-367``: la identidad, ``line_ids`` como recordset y las
hermanas de una línea leídas del recordset del plazo.
"""
from decimal import Decimal

import pytest

from addons.account.models import AccountPaymentTerm, AccountPaymentTermLine
from addons.base.models import ResCompany
from orm.models import BaseModel

pytestmark = pytest.mark.django_db


@pytest.fixture
def term():
    company = ResCompany.objects.create(
        name='Kaupamex', code='kaupamex_test_account_u3')
    return AccountPaymentTerm.objects.create(name='30/70', company=company)


def test_both_models_are_basemodels():
    assert issubclass(AccountPaymentTerm, BaseModel)
    assert issubclass(AccountPaymentTermLine, BaseModel)


def test_the_lines_of_a_term_are_a_recordset(term):
    first = AccountPaymentTermLine.objects.create(
        payment=term, value='percent', value_amount=Decimal('30'))
    lines = AccountPaymentTerm.objects.get(pk=term.pk).line_ids
    assert isinstance(lines, BaseModel)
    assert lines.ids == [first.id]


def test_a_new_line_takes_the_remaining_percent(term):
    AccountPaymentTermLine.objects.create(
        payment=term, value='percent', value_amount=Decimal('30'))
    second = AccountPaymentTermLine.objects.create(
        payment=term, value='percent', value_amount=Decimal('0'))
    second = AccountPaymentTermLine.objects.get(pk=second.pk)
    second._compute_value_amount()
    assert second.value_amount == Decimal('70')
