"""Contrato de ``AccountUpdateTaxTagsWizard`` — ≙ ``account.update.tax.tags.wizard``.

Portación fiel de ``odoo19c: addons/account_update_tax_tags/wizard/
account_update_tax_tags_wizard.py`` (``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``).
``TransientModel`` sin tabla — el estado del wizard lo pasa el llamador como
argumentos (ver el docstring del módulo portado).

Como el motor de "envoltura" que persiste ``tax_ids``/
``tax_repartition_line_id``/``tax_tag_ids`` en ``account.move.line`` no está
portado (ver ``models/account_move_line_tax_link.py``), estos tests
construyen ese estado DIRECTO sobre los tres modelos puente —equivalente a
lo que el motor de facturación de Odoo habría dejado tras postear— en vez de
pasar por un flujo de creación de factura que este árbol no tiene.

Requiere ``addons.account_update_tax_tags`` en ``INSTALLED_APPS`` (fuera del
alcance de este porte — ver ``apps.py``) para que la migración cree las
tres tablas puente.

Cobertura declarada — dos tests de la referencia NO se portan
===================================================================

``test_update_with_caba_taxes`` y ``test_update_caba_taxes_with_negative_
line`` dependen de ``tax_cash_basis_origin_move_id``/``tax_exigibility``,
ninguno portado en ``account.AccountMove``/``AccountTax`` de este árbol
(medido, ver el docstring del wizard). El resto de la matriz de la
referencia sí tiene test aquí: cómputo de fecha, candado fiscal, filtro por
fecha/empresa, múltiples impuestos, impuesto de grupo, impuestos hijos
compartidos entre padres, ``move_type='entry'`` con signo del saldo, casilla
ausente antes/después.
"""
from datetime import date
from decimal import Decimal

import pytest

from addons.account.models.account_account import AccountAccount
from addons.account.models.account_account_tag import AccountAccountTag
from addons.account.models.account_journal import AccountJournal
from addons.account.models.account_move import AccountMove
from addons.account.models.account_move_line import AccountMoveLine
from addons.account.models.account_tax import AccountTax
from addons.account.models.account_tax_repartition_line import AccountTaxRepartitionLine
from addons.account_update_tax_tags.models.account_move_line_tax_link import (
    AccountMoveLineTag,
    AccountMoveLineTax,
    AccountMoveLineTaxRepartition,
)
from addons.account_update_tax_tags.wizard.account_update_tax_tags_wizard import (
    AccountUpdateTaxTagsWizard,
)
from addons.base.models import ResCompany
from exceptions import UserError

pytestmark = pytest.mark.django_db


# ==== fixtures ==============================================================

@pytest.fixture
def company(db):
    return ResCompany.objects.create(code='acme', name='ACME')


@pytest.fixture
def journal(company):
    return AccountJournal.objects.create(
        name='Ventas', code='VEN', type='sale', company=company)


@pytest.fixture
def accounts(company):
    receivable = AccountAccount.objects.create(
        code='105', name='Clientes', account_type='asset_receivable', company=company)
    income = AccountAccount.objects.create(
        code='401', name='Ventas', account_type='income', company=company)
    tax_account = AccountAccount.objects.create(
        code='210', name='IVA por pagar', account_type='liability_current', company=company)
    return receivable, income, tax_account


# ==== helpers ================================================================

def _tag(name, country=None):
    tag, _created = AccountAccountTag.objects.get_or_create(
        name=name, applicability='taxes', country=country)
    return tag


def _create_tax(company, name, type_tax_use='sale', tag_names=None, children=None):
    """≙ ``_create_tax`` de la referencia (sin ``cash_basis_transfer_account``,
    no portado — ver docstring del módulo)."""
    tag_names = tag_names or {}
    tax = AccountTax.objects.create(
        name=name, amount=Decimal('15'),
        amount_type='group' if children else 'percent',
        type_tax_use=type_tax_use, company=company,
    )
    if children:
        tax.children.set(children)
        return tax
    for key, document_type, repartition_type in (
        ('invoice_base', 'invoice', 'base'),
        ('invoice_tax', 'invoice', 'tax'),
        ('refund_base', 'refund', 'base'),
        ('refund_tax', 'refund', 'tax'),
    ):
        rep_line = AccountTaxRepartitionLine.objects.create(
            tax=tax, document_type=document_type, repartition_type=repartition_type)
        tag_name = tag_names.get(key)
        if tag_name:
            rep_line.tag_ids.set([_tag(tag_name)])
    return tax


def _rep_line(tax, document_type, repartition_type):
    return AccountTaxRepartitionLine.objects.get(
        tax=tax, document_type=document_type, repartition_type=repartition_type)


def _move(company, journal, move_type='out_invoice', move_date=None, state='posted'):
    return AccountMove.objects.create(
        move_type=move_type, date=move_date or date(2023, 7, 1),
        journal=journal, company=company, state=state)


def _invoice_with_tax(company, journal, accounts, tax, move_type='out_invoice',
                       amount=Decimal('100.00'), move_date=None):
    """Base + línea de impuesto (invoice) + contrapartida — con sus puentes
    ``AccountMoveLineTax``/``AccountMoveLineTaxRepartition`` ya cableados,
    como si el motor de envoltura (no portado) las hubiera dejado así."""
    receivable, income, tax_account = accounts
    move = _move(company, journal, move_type=move_type, move_date=move_date)
    base_line = AccountMoveLine.objects.create(
        move=move, account=income, display_type='product', credit=amount)
    AccountMoveLineTax.objects.create(line=base_line, tax=tax)
    document_type = 'invoice' if move_type in ('out_invoice', 'in_invoice') else 'refund'
    tax_rep_line = _rep_line(tax, document_type, 'tax')
    tax_line = AccountMoveLine.objects.create(
        move=move, account=tax_account, display_type='tax', credit=amount * Decimal('0.15'))
    AccountMoveLineTaxRepartition.objects.create(line=tax_line, repartition_line=tax_rep_line)
    AccountMoveLine.objects.create(
        move=move, account=receivable, debit=amount + amount * Decimal('0.15'))
    return move, base_line, tax_line


def _tag_names(line):
    link_qs = AccountMoveLineTag.objects.filter(line=line).select_related('tag')
    return sorted(link.tag.name for link in link_qs)


# ==== compute methods ========================================================

class TestComputeDateFrom:
    def test_no_lock_date_defaults_to_today(self, company):
        assert AccountUpdateTaxTagsWizard.compute_date_from(company) == date.today()

    def test_lock_date_set_defaults_to_day_after(self, company):
        company.tax_lock_date = date(2023, 1, 31)
        company.save(update_fields=['tax_lock_date'])
        assert (AccountUpdateTaxTagsWizard.compute_date_from(company)
                == date(2023, 2, 1))


class TestDisplayLockDateWarning:
    def test_date_after_lock_date_no_warning(self, company):
        company.tax_lock_date = date(2023, 1, 31)
        company.save(update_fields=['tax_lock_date'])
        assert not AccountUpdateTaxTagsWizard.display_lock_date_warning(
            company, date(2023, 2, 1))

    def test_date_before_lock_date_warns(self, company):
        company.tax_lock_date = date(2023, 1, 31)
        company.save(update_fields=['tax_lock_date'])
        assert AccountUpdateTaxTagsWizard.display_lock_date_warning(
            company, date(2023, 1, 15))

    def test_no_lock_date_never_warns(self, company):
        assert not AccountUpdateTaxTagsWizard.display_lock_date_warning(
            company, date(2023, 1, 15))


# ==== update_amls_tax_tags ===================================================

class TestUpdateAmlsTaxTags:
    def test_base_and_tax_lines_get_the_configured_tags(
            self, company, journal, accounts):
        tax = _create_tax(company, 'iva_16', tag_names={
            'invoice_base': 'base_tag', 'invoice_tax': 'tax_tag',
        })
        _move_, base_line, tax_line = _invoice_with_tax(company, journal, accounts, tax)

        AccountUpdateTaxTagsWizard.update_amls_tax_tags(company, date(2023, 1, 1))

        assert _tag_names(base_line) == ['base_tag']
        assert _tag_names(tax_line) == ['tax_tag']

    def test_recomputes_after_the_tag_configuration_changes(
            self, company, journal, accounts):
        tax = _create_tax(company, 'iva_16', tag_names={'invoice_tax': 'old_tag'})
        _move_, _base_line, tax_line = _invoice_with_tax(
            company, journal, accounts, tax)
        # Estado previo (obsoleto), como si otra corrida ya lo hubiera dejado así.
        AccountMoveLineTag.objects.create(line=tax_line, tag=_tag('old_tag'))
        # Cambia la configuración del impuesto — sin tocar el apunte histórico.
        _rep_line(tax, 'invoice', 'tax').tag_ids.set([_tag('new_tag')])

        AccountUpdateTaxTagsWizard.update_amls_tax_tags(company, date(2023, 1, 1))

        assert _tag_names(tax_line) == ['new_tag']

    def test_refund_move_type_resolves_refund_tags(self, company, journal, accounts):
        tax = _create_tax(company, 'iva_16', tag_names={
            'invoice_base': 'inv_base', 'refund_base': 'ref_base',
        })
        _move_, base_line, _tax_line = _invoice_with_tax(
            company, journal, accounts, tax, move_type='out_refund')

        AccountUpdateTaxTagsWizard.update_amls_tax_tags(company, date(2023, 1, 1))

        assert _tag_names(base_line) == ['ref_base']

    def test_date_from_filters_out_earlier_lines(self, company, journal, accounts):
        tax = _create_tax(company, 'iva_16', tag_names={'invoice_base': 'base_tag'})
        _move_, base_line, _tax_line = _invoice_with_tax(
            company, journal, accounts, tax, move_date=date(2023, 1, 23))
        stale_tag = _tag('stale_tag')
        AccountMoveLineTag.objects.create(line=base_line, tag=stale_tag)

        AccountUpdateTaxTagsWizard.update_amls_tax_tags(company, date(2023, 2, 1))

        # La línea es anterior a date_from: la casilla obsoleta queda intacta.
        assert _tag_names(base_line) == ['stale_tag']

    def test_date_from_includes_the_boundary_date(self, company, journal, accounts):
        tax = _create_tax(company, 'iva_16', tag_names={'invoice_base': 'base_tag'})
        _move_, base_line, _tax_line = _invoice_with_tax(
            company, journal, accounts, tax, move_date=date(2023, 2, 1))

        AccountUpdateTaxTagsWizard.update_amls_tax_tags(company, date(2023, 2, 1))

        assert _tag_names(base_line) == ['base_tag']

    def test_multiple_taxes_on_one_line_aggregate_tags(self, company, journal, accounts):
        receivable, income, tax_account = accounts
        tax_1 = _create_tax(company, 'iva_16', tag_names={'invoice_base': 'tag_1'})
        tax_2 = _create_tax(company, 'ret_isr', tag_names={'invoice_base': 'tag_2'})
        move = _move(company, journal)
        base_line = AccountMoveLine.objects.create(
            move=move, account=income, display_type='product', credit=Decimal('100'))
        AccountMoveLineTax.objects.create(line=base_line, tax=tax_1)
        AccountMoveLineTax.objects.create(line=base_line, tax=tax_2)

        AccountUpdateTaxTagsWizard.update_amls_tax_tags(company, date(2023, 1, 1))

        assert _tag_names(base_line) == ['tag_1', 'tag_2']

    def test_only_the_targeted_company_is_updated(self, company, journal, accounts):
        other_company = ResCompany.objects.create(code='other', name='Other Co')
        other_journal = AccountJournal.objects.create(
            name='Ventas 2', code='VEN2', type='sale', company=other_company)
        other_receivable = AccountAccount.objects.create(
            code='105', name='Clientes', account_type='asset_receivable',
            company=other_company)
        other_income = AccountAccount.objects.create(
            code='401', name='Ventas', account_type='income', company=other_company)
        other_tax_account = AccountAccount.objects.create(
            code='210', name='IVA', account_type='liability_current',
            company=other_company)

        tax_1 = _create_tax(company, 'iva_16', tag_names={'invoice_base': 'tag_co1'})
        tax_2 = _create_tax(other_company, 'iva_16_other', tag_names={
            'invoice_base': 'tag_co2'})
        _move_1, line_1, _t1 = _invoice_with_tax(company, journal, accounts, tax_1)
        _move_2, line_2, _t2 = _invoice_with_tax(
            other_company, other_journal,
            (other_receivable, other_income, other_tax_account), tax_2)

        AccountUpdateTaxTagsWizard.update_amls_tax_tags(company, date(2023, 1, 1))

        assert _tag_names(line_1) == ['tag_co1']
        assert _tag_names(line_2) == []   # empresa ajena: sin tocar

    def test_group_tax_expands_to_children_own_tags(self, company, journal, accounts):
        receivable, income, tax_account = accounts
        child_1 = _create_tax(company, 'child_1', tag_names={'invoice_base': 'tag_c1'})
        child_2 = _create_tax(company, 'child_2', tag_names={'invoice_base': 'tag_c2'})
        parent = _create_tax(company, 'parent_group', children=[child_1, child_2])
        move = _move(company, journal)
        base_line = AccountMoveLine.objects.create(
            move=move, account=income, display_type='product', credit=Decimal('100'))
        AccountMoveLineTax.objects.create(line=base_line, tax=parent)

        AccountUpdateTaxTagsWizard.update_amls_tax_tags(company, date(2023, 1, 1))

        assert _tag_names(base_line) == ['tag_c1', 'tag_c2']

    def test_child_tax_shared_by_two_parents_raises(self, company, journal, accounts):
        shared_child = _create_tax(company, 'shared_child', tag_names={
            'invoice_base': 'shared_tag'})
        _create_tax(company, 'parent_1', children=[shared_child])
        _create_tax(company, 'parent_2', children=[shared_child])

        with pytest.raises(UserError):
            AccountUpdateTaxTagsWizard.update_amls_tax_tags(company, date(2023, 1, 1))

    def test_no_tag_before_gets_a_tag_after(self, company, journal, accounts):
        tax = _create_tax(company, 'iva_16', tag_names={'invoice_base': 'new_tag'})
        _move_, base_line, _tax_line = _invoice_with_tax(company, journal, accounts, tax)
        assert _tag_names(base_line) == []

        AccountUpdateTaxTagsWizard.update_amls_tax_tags(company, date(2023, 1, 1))

        assert _tag_names(base_line) == ['new_tag']

    def test_tag_removed_from_config_clears_the_line(self, company, journal, accounts):
        tax = _create_tax(company, 'iva_16', tag_names={'invoice_tax': 'tag_a'})
        _move_, _base_line, tax_line = _invoice_with_tax(company, journal, accounts, tax)
        AccountMoveLineTag.objects.create(line=tax_line, tag=_tag('tag_a'))
        _rep_line(tax, 'invoice', 'tax').tag_ids.clear()

        AccountUpdateTaxTagsWizard.update_amls_tax_tags(company, date(2023, 1, 1))

        assert _tag_names(tax_line) == []

    @pytest.mark.parametrize('type_tax_use,balance,expected_document_type', [
        ('sale', Decimal('-1000'), 'invoice'),
        ('sale', Decimal('1000'), 'refund'),
        ('purchase', Decimal('1000'), 'invoice'),
        ('purchase', Decimal('-1000'), 'refund'),
    ])
    def test_entry_move_type_resolves_by_balance_sign(
            self, company, journal, accounts, type_tax_use, balance,
            expected_document_type):
        receivable, income, tax_account = accounts
        tax = _create_tax(company, f'test_{type_tax_use}', type_tax_use=type_tax_use, tag_names={
            'invoice_base': 'invoice_tag', 'refund_base': 'refund_tag',
        })
        move = _move(company, journal, move_type='entry')
        line = AccountMoveLine.objects.create(
            move=move, account=income,
            debit=balance if balance > 0 else Decimal('0'),
            credit=-balance if balance < 0 else Decimal('0'))
        AccountMoveLineTax.objects.create(line=line, tax=tax)

        AccountUpdateTaxTagsWizard.update_amls_tax_tags(company, date(2023, 1, 1))

        expected_tag = 'invoice_tag' if expected_document_type == 'invoice' else 'refund_tag'
        assert _tag_names(line) == [expected_tag]

    def test_entry_move_type_with_none_type_tax_use_is_left_untouched(
            self, company, journal, accounts):
        receivable, income, tax_account = accounts
        tax = _create_tax(company, 'no_use', type_tax_use='none', tag_names={
            'invoice_base': 'irrelevant_tag'})
        move = _move(company, journal, move_type='entry')
        line = AccountMoveLine.objects.create(
            move=move, account=income, debit=Decimal('100'))
        AccountMoveLineTax.objects.create(line=line, tax=tax)

        result = AccountUpdateTaxTagsWizard.update_amls_tax_tags(company, date(2023, 1, 1))

        assert line.pk not in result
        assert _tag_names(line) == []

    def test_returns_the_impacted_aml_ids(self, company, journal, accounts):
        # Ambas líneas deben recibir una casilla REAL: un par (aml, None)
        # sin fila previa que borrar no cuenta como "impactado" — ver la
        # nota del paso 4 en el docstring del wizard.
        tax = _create_tax(company, 'iva_16', tag_names={
            'invoice_base': 'base_tag', 'invoice_tax': 'line_tax_tag'})
        _move_, base_line, tax_line = _invoice_with_tax(company, journal, accounts, tax)

        impacted = AccountUpdateTaxTagsWizard.update_amls_tax_tags(company, date(2023, 1, 1))

        assert impacted == sorted([base_line.pk, tax_line.pk])

    def test_a_pair_with_no_tag_and_nothing_to_delete_is_not_impacted(
            self, company, journal, accounts):
        # invoice_tax queda sin casilla configurada y el apunte no tenía
        # ninguna previa: (tax_line, None) se evalúa pero no cuenta como
        # impactado (nada se borra, nada se inserta).
        tax = _create_tax(company, 'iva_16', tag_names={'invoice_base': 'base_tag'})
        _move_, base_line, tax_line = _invoice_with_tax(company, journal, accounts, tax)

        impacted = AccountUpdateTaxTagsWizard.update_amls_tax_tags(company, date(2023, 1, 1))

        assert impacted == [base_line.pk]
