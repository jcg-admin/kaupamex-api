"""Contrato de los dos ganchos de numeración — ≙ ``_get_starting_sequence``/
``_get_last_sequence_domain`` de ``odoo19c: addons/account_debit_note/
models/account_move.py`` (``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``).

Extiende el mecanismo que ``tests/unit/account/test_account_move_sequence.py``
ya fija para ``AccountMove.post()`` — aquí sólo lo que ``account_debit_note``
le agrega: prefijo ``D`` + serie separada cuando el diario tiene
``debit_sequence``.

Requiere ``addons.account_debit_note`` en ``INSTALLED_APPS`` (fuera del
alcance de este porte — ver ``apps.py``) para que la migración cree las
tablas de ``JournalDebitSequence``/``AccountMoveDebitNote``. Los ganchos de
``AccountMove`` los cuelga en producción ``AccountDebitNoteConfig.ready()``;
aquí se invocan explícitamente una vez (idempotente — ver el docstring de
``account_move_sequence.py``).
"""
from decimal import Decimal

import pytest
from django.utils import timezone

from addons.account.models import (
    AccountAccount,
    AccountJournal,
    AccountMove,
    AccountMoveLine,
)
from addons.account_debit_note.models.account_journal import JournalDebitSequence
from addons.account_debit_note.models.account_move import AccountMoveDebitNote
from addons.account_debit_note.models.account_move_sequence import (
    apply_account_debit_note_extensions,
)
from addons.base.models import ResCompany

apply_account_debit_note_extensions()

pytestmark = pytest.mark.django_db


@pytest.fixture
def company(db):
    return ResCompany.objects.create(code='acme', name='ACME')


@pytest.fixture
def setup(db, company):
    journal = AccountJournal.objects.create(
        name='Ventas', code='VEN', type='sale', company=company)
    receivable = AccountAccount.objects.create(
        code='105', name='Clientes', account_type='asset_receivable',
        company=company)
    income = AccountAccount.objects.create(
        code='401', name='Ventas', account_type='income', company=company)
    return company, journal, receivable, income


def _balanced(company, journal, receivable, income,
              move_type='out_invoice', amount=Decimal('100.00')):
    move = AccountMove.objects.create(
        move_type=move_type, date=timezone.now().date(),
        journal=journal, company=company)
    AccountMoveLine.objects.create(move=move, account=receivable, debit=amount)
    AccountMoveLine.objects.create(move=move, account=income, credit=amount)
    return move


def _debit_note(setup, origin):
    """Crea (sin postear) una nota de débito vinculada a ``origin``."""
    debit_note = _balanced(*setup)
    AccountMoveDebitNote.objects.create(move=debit_note, origin=origin)
    return debit_note


class TestWithDedicatedSequence:
    """Diario ``sale`` — ``JournalDebitSequence.default_for_type`` es
    ``True`` sin necesidad de fila override (≙ el default de
    ``_compute_debit_sequence``)."""

    def test_first_debit_note_gets_the_d_prefix(self, setup):
        company, journal, receivable, income = setup
        origin = _balanced(*setup)
        origin.post()
        debit_note = _debit_note(setup, origin)
        debit_note.post()
        debit_note.refresh_from_db()
        assert debit_note.name == f'DINV/VEN/{debit_note.date.year}/00001'

    def test_debit_note_series_is_its_own(self, setup):
        """Una segunda nota de débito continúa SU serie (2), no la de las
        facturas normales — es lo que ``get_last_sequence_domain`` protege."""
        company, journal, receivable, income = setup
        origin_1 = _balanced(*setup)
        origin_1.post()
        debit_note_1 = _debit_note(setup, origin_1)
        debit_note_1.post()

        # Una factura NORMAL de por medio: mismo diario, mismo tipo, mismo
        # año — si el dominio no separara, "la última fila" sería ésta y la
        # segunda nota de débito heredaría el prefijo sin "D".
        middle_invoice = _balanced(*setup)
        middle_invoice.post()

        origin_2 = _balanced(*setup)
        origin_2.post()
        debit_note_2 = _debit_note(setup, origin_2)
        debit_note_2.post()
        debit_note_2.refresh_from_db()

        assert debit_note_2.name == f'DINV/VEN/{debit_note_2.date.year}/00002'

    def test_normal_invoices_do_not_inherit_the_debit_series(self, setup):
        """La factura creada DESPUÉS de la nota de débito sigue SU propia
        serie (2), no la de la nota de débito (1)."""
        company, journal, receivable, income = setup
        origin = _balanced(*setup)
        origin.post()                                     # INV/.../00001
        debit_note = _debit_note(setup, origin)
        debit_note.post()                                  # DINV/.../00001

        invoice_2 = _balanced(*setup)
        invoice_2.post()
        invoice_2.refresh_from_db()

        assert invoice_2.name == f'INV/VEN/{invoice_2.date.year}/00002'

    def test_credit_note_does_not_get_the_d_prefix(self, setup):
        """≙ ``move_type in ("in_invoice", "out_invoice")`` — una nota de
        crédito (``out_refund``) nunca lleva el prefijo, aunque el diario
        tenga secuencia dedicada."""
        company, journal, receivable, income = setup
        origin = _balanced(*setup)
        origin.post()
        refund = _balanced(*setup, move_type='out_refund')
        AccountMoveDebitNote.objects.create(move=refund, origin=origin)
        refund.post()
        refund.refresh_from_db()
        assert refund.name == f'RINV/VEN/{refund.date.year}/00001'


class TestWithoutDedicatedSequence:
    def test_debit_note_shares_the_series_when_the_journal_opts_out(self, setup):
        company, journal, receivable, income = setup
        JournalDebitSequence.objects.create(journal=journal, debit_sequence=False)

        origin = _balanced(*setup)
        origin.post()                                      # INV/.../00001
        debit_note = _debit_note(setup, origin)
        debit_note.post()
        debit_note.refresh_from_db()

        # Sin secuencia dedicada: comparte la serie de facturas normales,
        # sin prefijo "D".
        assert debit_note.name == f'INV/VEN/{debit_note.date.year}/00002'
