"""Contrato de los modelos fiscales del núcleo ``account`` — portación fiel
de Odoo (``odoo19c``, ``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``).

Cubre:

- ``AccountTaxGroup``: contrapartida de cierre de IVA.
- ``AccountTaxRepartitionLine``: reparto de un impuesto — prerrequisito de
  ``account_update_tax_tags``. ``factor`` y ``use_in_tax_closing`` computados.
- ``AccountFiscalPosition`` + ``AccountFiscalPositionAccount``: mapeo de
  cuentas e impuestos (``map_tax``/``map_account``). Sin
  ``account.fiscal.position.tax`` — retirado en 19 (ver docstring del módulo).
- ``AccountAccountTag``: casilla fiscal, único (name, applicability, country).
- ``AccountGroup``: agrupación jerárquica por rango de prefijo de código.
- ``account_root_*``: utilidades puras (NO modelo — ver docstring del módulo).
"""
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from addons.account.models import (
    AccountAccount,
    AccountAccountTag,
    AccountFiscalPosition,
    AccountFiscalPositionAccount,
    AccountGroup,
    AccountTax,
    AccountTaxGroup,
    AccountTaxRepartitionLine,
    account_root_from_code,
    account_root_name,
    account_root_parent,
)
from addons.base.models import ResCompany, ResCountry

pytestmark = pytest.mark.django_db


@pytest.fixture
def company():
    return ResCompany.objects.create(code='acme', name='ACME')


class TestAccountTaxGroup:
    def test_create_and_country_defaults_from_company(self, company):
        mx = ResCountry.objects.get_or_create(code='MX', defaults={'name': 'México'})[0]
        company.country = mx
        group = AccountTaxGroup.objects.create(name='IVA', company=company)
        assert group.country_id == mx.pk

    def test_payable_receivable_accounts(self, company):
        payable = AccountAccount.objects.create(
            code='210', name='IVA por pagar', account_type='liability_current',
            company=company)
        group = AccountTaxGroup.objects.create(
            name='IVA', company=company, tax_payable_account=payable)
        assert group.tax_payable_account_id == payable.pk


class TestAccountTaxRepartitionLine:
    def test_factor_computed_from_percent(self, company):
        tax = AccountTax.objects.create(name='IVA 16', company=company)
        line = AccountTaxRepartitionLine.objects.create(
            tax=tax, document_type='invoice', factor_percent=50)
        assert line.factor == pytest.approx(0.5)

    def test_company_derived_from_tax(self, company):
        tax = AccountTax.objects.create(name='IVA 16', company=company)
        line = AccountTaxRepartitionLine.objects.create(
            tax=tax, document_type='invoice')
        assert line.company_id == company.pk

    def test_use_in_tax_closing_excludes_income_expense(self, company):
        tax = AccountTax.objects.create(name='IVA 16', company=company)
        income = AccountAccount.objects.create(
            code='401', name='Ventas', account_type='income', company=company)
        payable = AccountAccount.objects.create(
            code='210', name='IVA por pagar', account_type='liability_current',
            company=company)
        line_income = AccountTaxRepartitionLine.objects.create(
            tax=tax, document_type='invoice', repartition_type='tax', account=income)
        line_payable = AccountTaxRepartitionLine.objects.create(
            tax=tax, document_type='invoice', repartition_type='tax', account=payable)
        line_base = AccountTaxRepartitionLine.objects.create(
            tax=tax, document_type='invoice', repartition_type='base')
        assert line_income.use_in_tax_closing is False
        assert line_payable.use_in_tax_closing is True
        assert line_base.use_in_tax_closing is False


class TestAccountAccountTag:
    def test_create(self, company):
        tag = AccountAccountTag.objects.create(name='+base', applicability='taxes')
        assert tag.applicability == 'taxes'

    def test_unique_name_applicability_country(self):
        # UNIQUE SQL: NULL != NULL (mismo comportamiento que la referencia,
        # `_name_uniq = 'unique(name, applicability, country_id)'`). Se
        # ejercita con country no-nulo para que el constraint aplique.
        mx = ResCountry.objects.get_or_create(code='MX', defaults={'name': 'México'})[0]
        AccountAccountTag.objects.create(name='+base', applicability='taxes', country=mx)
        with transaction.atomic(), pytest.raises(IntegrityError):
            AccountAccountTag.objects.create(name='+base', applicability='taxes', country=mx)


class TestAccountFiscalPosition:
    def test_map_account(self, company):
        src = AccountAccount.objects.create(
            code='401', name='Ventas nacional', account_type='income', company=company)
        dest = AccountAccount.objects.create(
            code='402', name='Ventas exportación', account_type='income', company=company)
        position = AccountFiscalPosition.objects.create(name='Extranjero', company=company)
        AccountFiscalPositionAccount.objects.create(
            position=position, account_src=src, account_dest=dest)
        assert position.map_account(src) == dest
        other = AccountAccount.objects.create(
            code='403', name='Otra', account_type='income', company=company)
        assert position.map_account(other) == other

    def test_fiscal_position_account_company_derived(self, company):
        src = AccountAccount.objects.create(
            code='401', name='A', account_type='income', company=company)
        dest = AccountAccount.objects.create(
            code='402', name='B', account_type='income', company=company)
        position = AccountFiscalPosition.objects.create(name='Extranjero', company=company)
        mapping = AccountFiscalPositionAccount.objects.create(
            position=position, account_src=src, account_dest=dest)
        assert mapping.company_id == company.pk

    def test_map_tax_identity_without_position(self, company):
        position = AccountFiscalPosition()
        tax = AccountTax.objects.create(name='IVA 16', company=company)
        result = position.map_tax(AccountTax.objects.filter(pk=tax.pk))
        assert list(result) == [tax]

    def test_map_tax_excludes_taxes_with_other_positions_when_no_tax_ids(self, company):
        position = AccountFiscalPosition.objects.create(name='Extranjero', company=company)
        universal = AccountTax.objects.create(name='IVA universal', company=company)
        restricted = AccountTax.objects.create(name='IVA doméstico', company=company)
        other_position = AccountFiscalPosition.objects.create(name='Otra', company=company)
        restricted.fiscal_positions.add(other_position)
        result = position.map_tax(AccountTax.objects.filter(pk__in=[universal.pk, restricted.pk]))
        assert list(result) == [universal]

    def test_map_tax_substitutes_domestic_for_replacement(self, company):
        # Rama de sustitución (H-API-322) — antes inerte: _compute_tax_map
        # devolvía {} siempre porque original_tax_ids no estaba portado.
        domestic = AccountTax.objects.create(name='IVA 16 doméstico', company=company)
        export = AccountTax.objects.create(name='IVA 0 exportación', company=company)
        export.original_tax_ids.add(domestic)
        position = AccountFiscalPosition.objects.create(name='Extranjero', company=company)
        position.tax_ids.add(export)
        result = position.map_tax(AccountTax.objects.filter(pk=domestic.pk))
        assert list(result) == [export]
        # El reverso se puebla solo — misma tabla ``account_tax_alternatives``,
        # leída en la otra dirección (Odoo replacing_tax_ids, readonly).
        assert list(domestic.replacing_tax_ids.all()) == [export]

    def test_map_tax_leaves_taxes_outside_the_map_untouched(self, company):
        domestic = AccountTax.objects.create(name='IVA 16 doméstico', company=company)
        export = AccountTax.objects.create(name='IVA 0 exportación', company=company)
        unrelated = AccountTax.objects.create(name='Retención', company=company)
        export.original_tax_ids.add(domestic)
        position = AccountFiscalPosition.objects.create(name='Extranjero', company=company)
        position.tax_ids.add(export)
        result = position.map_tax(AccountTax.objects.filter(pk__in=[domestic.pk, unrelated.pk]))
        assert set(result) == {export, unrelated}

    def test_compute_tax_map_empty_without_original_tax_ids(self, company):
        export = AccountTax.objects.create(name='IVA 0 exportación', company=company)
        position = AccountFiscalPosition.objects.create(name='Extranjero', company=company)
        position.tax_ids.add(export)
        assert position._compute_tax_map() == {}


class TestAccountGroup:
    def test_prefix_cross_default(self, company):
        group = AccountGroup.objects.create(
            name='Bancos', code_prefix_start='10', company=company)
        assert group.code_prefix_end == '10'

    def test_parent_adopted_from_more_specific_prefix(self, company):
        parent = AccountGroup.objects.create(
            name='Activo', code_prefix_start='1', code_prefix_end='1', company=company)
        child = AccountGroup.objects.create(
            name='Bancos', code_prefix_start='10', code_prefix_end='19', company=company)
        assert child.parent_id == parent.pk

    def test_self_parent_rejected(self, company):
        group = AccountGroup.objects.create(
            name='Activo', code_prefix_start='1', company=company)
        group.parent = group
        with pytest.raises(ValidationError):
            group.clean()

    def test_prefix_length_mismatch_rejected_by_clean(self, company):
        # H-API-323 / tarea #113 — _check_length_prefix (odoo19c: 1510-1513).
        # Longitudes distintas entre inicio y fin del rango.
        group = AccountGroup(
            name='Activo', code_prefix_start='10', code_prefix_end='100',
            company=company)
        with pytest.raises(ValidationError) as exc:
            group.clean()
        assert exc.value.message_dict['code_prefix_end'] == [
            'ACCOUNT_GROUP_PREFIX_LENGTH_MISMATCH']

    def test_prefix_length_match_accepted_by_clean(self, company):
        group = AccountGroup(
            name='Activo', code_prefix_start='10', code_prefix_end='19',
            company=company)
        group.clean()  # no debe lanzar

    def test_prefix_length_mismatch_rejected_by_db_constraint(self, company):
        # El CheckConstraint de Meta.constraints es la garantía real —
        # se cumple sin pasar por clean() (p. ej. bulk_create/update).
        with transaction.atomic(), pytest.raises(IntegrityError):
            AccountGroup.objects.create(
                name='Activo', code_prefix_start='10', code_prefix_end='100',
                company=company)

    def test_prefix_overlap_rejected(self, company):
        # H-API-323 / tarea #113 — _constraint_prefix_overlap
        # (odoo19c: 1549-1568). Misma granularidad (longitud 2), rango
        # [10, 19] ya existe; [15, 25] se solapa en 15-19.
        AccountGroup.objects.create(
            name='Bancos', code_prefix_start='10', code_prefix_end='19',
            company=company)
        overlapping = AccountGroup(
            name='Otro', code_prefix_start='15', code_prefix_end='25',
            company=company)
        with pytest.raises(ValidationError) as exc:
            overlapping.clean()
        assert exc.value.message_dict['code_prefix_start'] == [
            'ACCOUNT_GROUP_PREFIX_OVERLAP']

    def test_prefix_no_overlap_accepted(self, company):
        AccountGroup.objects.create(
            name='Bancos', code_prefix_start='10', code_prefix_end='19',
            company=company)
        disjoint = AccountGroup(
            name='Otro', code_prefix_start='20', code_prefix_end='29',
            company=company)
        disjoint.clean()  # no debe lanzar

    def test_prefix_overlap_ignores_different_granularity(self, company):
        # Distinta longitud de prefijo => distinta granularidad; Odoo NO
        # los compara entre sí (char_length(other.start) == char_length(this.start)).
        AccountGroup.objects.create(
            name='Activo', code_prefix_start='1', code_prefix_end='1',
            company=company)
        child = AccountGroup(
            name='Bancos', code_prefix_start='10', code_prefix_end='19',
            company=company)
        child.clean()  # no debe lanzar: '1' (longitud 1) no es par de '10' (longitud 2)

    def test_prefix_overlap_ignores_other_company(self, company):
        other_company = ResCompany.objects.create(code='other', name='Other')
        AccountGroup.objects.create(
            name='Bancos', code_prefix_start='10', code_prefix_end='19',
            company=other_company)
        same_range_other_company = AccountGroup(
            name='Bancos', code_prefix_start='10', code_prefix_end='19',
            company=company)
        same_range_other_company.clean()  # no debe lanzar: empresa distinta


class TestAccountRoot:
    def test_from_account_code(self):
        assert account_root_from_code('601001') == '60'

    def test_parent_chain(self):
        assert account_root_parent('60') == '6'
        assert account_root_parent('6') is None

    def test_name_is_id(self):
        assert account_root_name('60') == '60'
