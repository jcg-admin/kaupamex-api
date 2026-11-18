"""La línea de método de pago de ``account.payment``.

≙ ``payment_method_line_id`` y su cómputo
(``odoo19c: addons/account/models/account_payment.py:74`` y ``:565``),
``available_payment_method_line_ids`` (``:85`` y ``:585``),
``payment_method_id`` (``:87``), ``payment_method_code`` (``:176``) y
``outstanding_account_id`` (``:123`` y ``:620``).
Diseño en ``designs/payment-method-line-field.md`` del Workbench.

Métrica: los campos del pago leídos de la base tras ``flush_all``.
Ciega a: los lectores de la línea fuera de esta cadena, que entran con el
porte de cada método que los contiene.
"""
from decimal import Decimal

import pytest
from django.apps import apps as django_apps
from django.db import connection

from addons.account.data import seed_manual_payment_methods
from addons.account.models import (
    AccountAccount, AccountJournal, AccountPayment)
from addons.base.models import ResCompany, ResPartner
from exceptions import ValidationError
from orm.environments import env, sudo

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _as_superuser():
    with sudo():
        yield


@pytest.fixture
def manual():
    """Los métodos manuales; la suite vacía las filas de migración."""
    return seed_manual_payment_methods(django_apps, connection.alias)


@pytest.fixture
def company():
    return ResCompany.objects.create(code='pmlf', name='PMLF')


def _journal(company, code, journal_type='bank'):
    return AccountJournal.create({'name': f'Diario {code}', 'code': code,
                                  'type': journal_type,
                                  'company_id': company.pk})


def _payment(journal, **values):
    payment = env()['account.payment'].create({
        'amount': Decimal('10.00'), 'journal': journal.id,
        'company': journal.company_id, **values})
    env().flush_all()
    return payment


def _stored(payment, *names):
    env().flush_all()
    return AccountPayment.objects.filter(pk=payment.id).values_list(
        *names).get()


def test_an_inbound_payment_takes_the_manual_inbound_line(manual, company):
    inbound, _outbound = manual
    journal = _journal(company, 'PM1')
    [line] = journal.inbound_payment_method_line_ids
    payment = _payment(journal)
    assert _stored(payment, 'payment_method_line_id',
                   'payment_method_id') == (line.id, inbound.pk)
    assert payment.payment_method_code == 'manual'


def test_an_outbound_payment_takes_the_outbound_line(manual, company):
    journal = _journal(company, 'PM2')
    [line] = journal.outbound_payment_method_line_ids
    payment = _payment(journal, payment_type='outbound')
    assert _stored(payment, 'payment_method_line_id') == (line.id,)


def _second_inbound_line(journal, manual):
    inbound, _outbound = manual
    # El cómputo del diario vacía y vuelve a crear sus líneas: se lee antes
    # para que no quede pendiente y se lleve la que se añade aquí.
    assert journal.inbound_payment_method_line_ids
    env().flush_all()
    line = env()['account.payment.method.line'].create({
        'name': 'Segunda', 'payment_method': inbound.pk,
        'journal': journal.id, 'sequence': 20})
    env().flush_all()
    return line


def test_the_partner_preferred_line_wins_when_available(manual, company):
    journal = _journal(company, 'PM3')
    preferred = _second_inbound_line(journal, manual)
    partner = ResPartner.objects.create(
        name='Con preferida',
        property_inbound_payment_method_line_id_id=preferred.id)
    payment = _payment(journal, partner=partner.pk)
    assert _stored(payment, 'payment_method_line_id') == (preferred.id,)


def test_a_preferred_line_of_another_journal_is_ignored(manual, company):
    journal = _journal(company, 'PM4')
    other = _journal(company, 'PM5')
    [first] = journal.inbound_payment_method_line_ids
    [foreign] = other.inbound_payment_method_line_ids
    partner = ResPartner.objects.create(
        name='Preferida ajena',
        property_inbound_payment_method_line_id_id=foreign.id)
    payment = _payment(journal, partner=partner.pk)
    assert _stored(payment, 'payment_method_line_id') == (first.id,)


def test_a_journal_without_lines_is_refused(manual, company):
    """≙ ``_check_payment_method_line_id`` (``:863``), primera rama: el
    cómputo deja el campo vacío y la restricción lo rehúsa."""
    journal = _journal(company, 'PM6', 'general')
    with pytest.raises(ValidationError, match='Please define a payment'):
        _payment(journal)


def test_a_line_of_another_journal_is_refused(manual, company):
    """Segunda rama: la línea escrita a mano tiene diario y no es el del
    pago."""
    journal = _journal(company, 'PM9')
    other = _journal(company, 'PM0')
    [foreign] = other.inbound_payment_method_line_ids
    payment = _payment(journal)
    with pytest.raises(ValidationError, match='is not available'):
        payment.write({'payment_method_line_id': foreign.id})
        env().flush_all()


def test_a_line_without_journal_is_accepted(manual, company):
    """La segunda rama sólo mira las líneas que tienen diario."""
    inbound, _outbound = manual
    journal = _journal(company, 'PMA')
    loose = env()['account.payment.method.line'].create({
        'name': 'Suelta', 'payment_method': inbound.pk})
    payment = _payment(journal)
    payment.write({'payment_method_line_id': loose.id})
    assert _stored(payment, 'payment_method_line_id') == (loose.id,)


def test_the_outstanding_account_follows_the_line(manual, company):
    journal = _journal(company, 'PM7')
    [line] = journal.inbound_payment_method_line_ids
    account = AccountAccount.objects.create(
        code='PMLF-OUT', name='Pagos pendientes',
        account_type='asset_current', company=company)
    line.write({'payment_account': account.pk})
    payment = _payment(journal)
    assert _stored(payment, 'outstanding_account_id') == (account.pk,)


def test_codes_to_exclude_is_empty_and_for_one_record(manual, company):
    journal = _journal(company, 'PM8')
    payment = _payment(journal)
    assert payment._get_payment_method_codes_to_exclude() == []
    with pytest.raises(ValueError):
        (payment + _payment(journal))._get_payment_method_codes_to_exclude()
