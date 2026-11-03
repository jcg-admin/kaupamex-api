"""Las claves que ``_format_strings`` ofrece a una cadena de formato.

≙ ``_format_strings`` (``odoo19c:
addons/account/wizard/account_automatic_entry_wizard.py:543-556``, LGPL-3): el
monto pasa por ``formatLang`` con la moneda de la compañía, ``debit_credit``
dice de qué lado cae, y ``date`` y ``new_date`` salen de ``format_date``; sin
fecha nueva, ``[Not set]``. Las claves de chatter (``link``,
``account_source_name``, ``account_target_name``) no se portan: sus mensajes
viven en el chatter de ``account.move``, que no está portado.

La fecha del caso tiene día mayor que doce para que ``%m/%d/%Y`` y el ISO no
coincidan, y el monto tiene miles para que se vea la agrupación.
"""

from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from addons.account.models import AccountJournal, AccountMove
from addons.account.wizard.account_automatic_entry_wizard import (
    AccountAutomaticEntryWizard,
)
from addons.base.models import ResCompany
from addons.base.models.res_currency import ResCurrency
from orm.environments import Environment, user_scope
from orm.utils import SUPERUSER_ID

pytestmark = [pytest.mark.unit, pytest.mark.django_db]

KEYS = '{amount}|{debit_credit}|{date}|{new_date}'


@pytest.fixture
def move(db):
    user = get_user_model().objects.create_user(
        login='corte.formato@kaupamex.mx', password='Corte123!')
    currency, _ = ResCurrency.objects.get_or_create(
        name='MXN', defaults={'symbol': '$'})
    company = ResCompany.objects.create(code='corte', name='Corte',
                                        currency=currency)
    journal = AccountJournal.objects.create(
        name='Varios', code='VAR', type='general', company=company)
    with Environment(None, SUPERUSER_ID, {}), user_scope(user.pk):
        yield AccountMove.objects.create(
            move_type='entry', company=company, journal=journal,
            date=date(2026, 1, 31))


def _amount(move, text):
    symbol = move.company.currency.symbol
    if move.company.currency.position == 'after':
        return f'{text}\N{NO-BREAK SPACE}{symbol}'
    return f'{symbol}\N{NO-BREAK SPACE}{text}'


def test_a_debit_amount_and_both_dates(move):
    text = AccountAutomaticEntryWizard._format_strings(
        KEYS, move, 100.0, Decimal('1234.5'), new_date=date(2026, 2, 28))
    assert text == f'{_amount(move, "1,234.50")}|D|01/31/2026|02/28/2026'


def test_a_credit_amount_without_new_date(move):
    text = AccountAutomaticEntryWizard._format_strings(
        KEYS, move, 100.0, Decimal('-1234.5'))
    assert text == f'{_amount(move, "1,234.50")}|C|01/31/2026|[Not set]'


def test_without_amount_both_amount_keys_are_empty(move):
    text = AccountAutomaticEntryWizard._format_strings(
        '{amount}|{debit_credit}', move, 100.0)
    assert text == '|None'
