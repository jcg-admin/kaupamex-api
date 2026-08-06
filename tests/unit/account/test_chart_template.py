"""Cargar el plan contable genérico en una empresa (#140, :ref:`h-api-348`).

Espeja el propósito de ``odoo19c: account/models/chart_template.py``: una
empresa recién creada no tiene cuentas ni impuestos, y el plan es lo que la
deja operable. Hasta ahora ``account`` no sembraba **nada** — 0 cuentas, 0
impuestos, 0 diarios—, que es la causa de fondo de :ref:`h-api-344`.

Lo que se fija aquí es el mecanismo, no el contenido de las tablas: que los
registros nazcan con identificador externo **por empresa**, que las referencias
entre ellos se resuelvan por ese nombre, y que dos empresas obtengan planos
independientes.
"""
import pytest

from addons.account.models import (
    AccountAccount,
    AccountFiscalPosition,
    AccountJournal,
    AccountReconcileModel,
    AccountTax,
    AccountTaxGroup,
    ChartTemplate,
)
from addons.account.models.chart_template import TEMPLATE_REGISTRY, template
from addons.account.models.account_tax_repartition_line import AccountTaxRepartitionLine
from addons.base.models.ir_model import IrModelData
from addons.base.models.res_company import ResCompany

pytestmark = [pytest.mark.unit]


@pytest.fixture
def company(db):
    return ResCompany.objects.create(code='acme', name='ACME')


@pytest.mark.django_db
class TestRegistry:
    def test_generic_chart_is_registered(self, db):
        """Importar el módulo de la plantilla la registra — sin barrer clases."""
        assert 'generic_coa' in ChartTemplate.get_chart_template_mapping()

    def test_generic_wins_without_country(self, db):
        assert ChartTemplate.guess_chart_template(None) == 'generic_coa'


@pytest.mark.django_db
class TestLoading:
    def test_loads_the_four_families(self, company):
        ChartTemplate.try_loading('generic_coa', company)

        assert AccountAccount.objects.filter(company=company).count() == 46
        assert AccountTaxGroup.objects.filter(company=company).count() == 2
        assert AccountTax.objects.filter(company=company).count() == 4
        assert AccountFiscalPosition.objects.filter(company=company).count() == 2

    def test_each_record_gets_its_external_id(self, company):
        ChartTemplate.try_loading('generic_coa', company)

        account = ChartTemplate.ref('receivable', company)
        assert account.code == '1210'
        assert IrModelData.objects.filter(
            module='account', name=f'{company.pk}_receivable').exists()

    def test_tax_points_to_its_group(self, company):
        """La referencia entre registros se resuelve **por nombre**, no por id.

        Es lo que el CSV expresa con ``tax_group_id=tax_group_15``: sin el
        identificador externo esa columna no significa nada.
        """
        ChartTemplate.try_loading('generic_coa', company)

        tax = ChartTemplate.ref('sale_tax_template', company)
        assert tax.tax_group == ChartTemplate.ref('tax_group_15', company)
        assert tax.amount == 15
        assert tax.type_tax_use == 'sale'

    def test_repartition_lines_are_created_with_the_tax(self, company):
        """Cuatro filas del CSV con ``id`` vacío son cuatro líneas hijas.

        Dos de factura (base + impuesto) y dos de rectificativa. La línea de
        impuesto apunta a la cuenta donde se acumula lo recaudado.
        """
        ChartTemplate.try_loading('generic_coa', company)

        tax = ChartTemplate.ref('sale_tax_template', company)
        lines = AccountTaxRepartitionLine.objects.filter(tax=tax)
        assert lines.count() == 4
        assert lines.filter(document_type='invoice').count() == 2
        assert lines.filter(document_type='refund').count() == 2

        received = ChartTemplate.ref('tax_received', company)
        tax_line = lines.filter(repartition_type='tax', document_type='invoice')
        assert tax_line.get().account == received

    def test_company_ends_up_with_default_taxes(self, company):
        """El paso que cierra la carga: la empresa **configurada**.

        Es exactamente el hueco de :ref:`h-api-344` — nadie sembraba un
        impuesto, así que ``account_sale_tax`` no tenía de dónde salir.
        """
        ChartTemplate.try_loading('generic_coa', company)
        company.refresh_from_db()

        assert company.account_sale_tax == ChartTemplate.ref(
            'sale_tax_template', company)
        assert company.account_purchase_tax == ChartTemplate.ref(
            'purchase_tax_template', company)


@pytest.mark.django_db
class TestBaseTemplate:
    """Los diarios no pertenecen a un plan: pertenecen a *tener* contabilidad.

    Se declaran con ``@template(model=...)`` sin código, y el resolutor los
    aplica a todo plan — ``[None] + parents`` en la referencia.
    """

    def test_company_receives_the_six_journals(self, company):
        ChartTemplate.try_loading('generic_coa', company)

        journals = AccountJournal.objects.filter(company=company)
        assert journals.count() == 6
        assert set(journals.values_list('code', flat=True)) == {
            'INV', 'BILL', 'MISC', 'EXCH', 'CABA', 'BNK1'}

    def test_reconcile_models_are_created_with_their_line(self, company):
        """Transferencia interna y comisión bancaria, cada una con su línea.

        Las hijas se declaran como lista de diccionarios; el cargador las crea
        igual que las de reparto del CSV.
        """
        ChartTemplate.try_loading('generic_coa', company)

        rules = AccountReconcileModel.objects.filter(company=company)
        assert rules.count() == 2

        fee_rule = ChartTemplate.ref('bank_fees_reco', company)
        assert fee_rule.match_label == 'contains'
        assert fee_rule.line_ids.count() == 1
        assert fee_rule.line_ids.get().amount_string == '100'

    def test_journals_carry_the_three_dashboard_fields(self, company):
        """``sequence``, ``show_on_dashboard`` y ``color`` — de la referencia.

        Una versión anterior los omitía diciendo que "el modelo no los tiene".
        Eso describía nuestro estado, no una incapacidad: los tres existen en
        ``odoo19c`` (``account_journal.py:147`` y
        ``account_journal_dashboard.py:30-31``) y Django los declara igual.
        """
        ChartTemplate.try_loading('generic_coa', company)

        sale_journal = AccountJournal.objects.get(company=company, type='sale')
        assert (sale_journal.sequence, sale_journal.show_on_dashboard, sale_journal.color) == (5, True, 11)

        misc_journal = AccountJournal.objects.get(company=company, code='MISC')
        assert misc_journal.show_on_dashboard is False

    def test_journals_come_out_in_reference_order(self, company):
        """``_order = 'sequence, type, code'`` — no ``code`` a secas."""
        ChartTemplate.try_loading('generic_coa', company)

        codes = list(
            AccountJournal.objects.filter(company=company).values_list('code', flat=True))
        assert codes[:3] == ['INV', 'BILL', 'BNK1']

    def test_sale_journal_is_the_one_the_entry_looks_up(self, company):
        """``create_invoice_from_subscription`` busca por ``type='sale'``.

        Es el consumidor real: sin un diario de ese tipo lanza ``UserError`` y
        el cobro no se puede asentar.
        """
        ChartTemplate.try_loading('generic_coa', company)

        sale_journal = AccountJournal.objects.get(company=company, type='sale')
        assert sale_journal.code == 'INV'
        assert sale_journal == ChartTemplate.ref('sale', company)


@pytest.mark.django_db
class TestLoadOnCompanyCreate:
    """El cargador sin consumidor no vale: una empresa hija hereda el plan.

    ≙ el ``create`` de la referencia, que instancia el plan de la raíz. Una
    empresa **raíz** no entra por aquí — su plan lo elige quien la aprovisiona.
    """

    def test_subsidiary_inherits_root_chart(self, company):
        company.chart_template = 'generic_coa'
        company.save(update_fields=['chart_template'])

        subsidiary = ResCompany.objects.create(
            code='acme-mx', name='ACME México', parent=company)

        assert AccountAccount.objects.filter(company=subsidiary).count() == 46
        assert AccountJournal.objects.filter(company=subsidiary, type='sale').exists()

    def test_nothing_loads_without_a_chart_on_the_root(self, company):
        """El receptor es no-op mientras nadie declare un plan.

        Es lo que hace que cablearlo no cambie el comportamiento de ninguna
        empresa existente.
        """
        assert company.chart_template is None

        subsidiary = ResCompany.objects.create(
            code='acme-co', name='ACME Colombia', parent=company)

        assert AccountAccount.objects.filter(company=subsidiary).count() == 0

    def test_root_does_not_load_itself(self, db):
        """Una raíz es su propio ``parent_ids[0]`` — sin el guard se cargaría sola."""
        root = ResCompany.objects.create(
            code='beta-root', name='BETA', chart_template='generic_coa')

        assert AccountAccount.objects.filter(company=root).count() == 0


@pytest.mark.django_db
class TestCompanyIsolation:
    def test_two_companies_get_independent_charts(self, company):
        """``receivable`` no nombra una cuenta: nombra un papel.

        La cuenta concreta es la de cada empresa, y por eso el identificador
        externo lleva su id delante.
        """
        other = ResCompany.objects.create(code='beta', name='BETA')
        ChartTemplate.try_loading('generic_coa', company)
        ChartTemplate.try_loading('generic_coa', other)

        first = ChartTemplate.ref('receivable', company)
        second = ChartTemplate.ref('receivable', other)
        assert first != second
        assert first.code == second.code == '1210'
        assert first.company == company and second.company == other

    def test_reloading_does_not_duplicate(self, company):
        """Idempotente por identificador externo, como la referencia."""
        ChartTemplate.try_loading('generic_coa', company)
        ChartTemplate.try_loading('generic_coa', company)

        assert AccountAccount.objects.filter(company=company).count() == 46


@pytest.mark.django_db
class TestRegistryComposes:
    """Dos declaraciones al mismo ``(codigo, modelo)`` se **componen**.

    ≙ ``_template_register``, un ``defaultdict(list)``
    (``odoo19c: chart_template.py:78-88``). Una versión anterior de este puerto
    guardaba una sola función por clave: la segunda declaración borraba a la
    primera **en silencio**, que es el modo de fallo que este test fija.
    """

    def test_second_declaration_does_not_erase_the_first(self, company):
        @template(model='account.journal')
        def extra_journal(cls, template_code):
            return {'extra': {
                'name': 'Diario extra', 'type': 'general', 'code': 'XTRA'}}

        try:
            ChartTemplate.try_loading('generic_coa', company)
            codes = set(AccountJournal.objects
                          .filter(company=company).values_list('code', flat=True))
            assert 'XTRA' in codes          # la nueva entró
            assert 'INV' in codes           # y la base sigue ahí
        finally:
            TEMPLATE_REGISTRY[None]['account.journal'].remove(extra_journal)

    def test_template_receives_the_chart_code(self, company):
        """La firma ``(cls, template_code)`` no es decorativa.

        Una plantilla **base** sirve a cualquier plan; sin el parámetro no
        podría saber a cuál está sirviendo.
        """
        seen = []

        @template(model='account.journal')
        def spy(cls, template_code):
            seen.append(template_code)
            return {}

        try:
            ChartTemplate.try_loading('generic_coa', company)
            assert seen == ['generic_coa']
        finally:
            TEMPLATE_REGISTRY[None]['account.journal'].remove(spy)
