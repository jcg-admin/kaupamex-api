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
    AccountTax,
    AccountTaxGroup,
    ChartTemplate,
)
from addons.account.models.account_tax_repartition_line import AccountTaxRepartitionLine
from addons.base.models.ir_model import IrModelData
from addons.base.models.res_company import ResCompany

pytestmark = [pytest.mark.unit]


@pytest.fixture
def company(db):
    return ResCompany.objects.create(code='acme', name='ACME')


@pytest.mark.django_db
class TestRegistro:
    def test_el_plan_generico_esta_registrado(self, db):
        """Importar el módulo de la plantilla la registra — sin barrer clases."""
        assert 'generic_coa' in ChartTemplate.get_chart_template_mapping()

    def test_sin_pais_el_generico_va_primero(self, db):
        assert ChartTemplate.guess_chart_template(None) == 'generic_coa'


@pytest.mark.django_db
class TestCarga:
    def test_carga_las_cuatro_familias(self, company):
        ChartTemplate.try_loading('generic_coa', company)

        assert AccountAccount.objects.filter(company=company).count() == 46
        assert AccountTaxGroup.objects.filter(company=company).count() == 2
        assert AccountTax.objects.filter(company=company).count() == 4
        assert AccountFiscalPosition.objects.filter(company=company).count() == 2

    def test_cada_registro_nace_con_su_identificador(self, company):
        ChartTemplate.try_loading('generic_coa', company)

        cuenta = ChartTemplate.ref('receivable', company)
        assert cuenta.code == '1210'
        assert IrModelData.objects.filter(
            module='account', name=f'{company.pk}_receivable').exists()

    def test_el_impuesto_apunta_a_su_grupo(self, company):
        """La referencia entre registros se resuelve **por nombre**, no por id.

        Es lo que el CSV expresa con ``tax_group_id=tax_group_15``: sin el
        identificador externo esa columna no significa nada.
        """
        ChartTemplate.try_loading('generic_coa', company)

        impuesto = ChartTemplate.ref('sale_tax_template', company)
        assert impuesto.tax_group == ChartTemplate.ref('tax_group_15', company)
        assert impuesto.amount == 15
        assert impuesto.type_tax_use == 'sale'

    def test_las_lineas_de_reparto_nacen_con_el_impuesto(self, company):
        """Cuatro filas del CSV con ``id`` vacío son cuatro líneas hijas.

        Dos de factura (base + impuesto) y dos de rectificativa. La línea de
        impuesto apunta a la cuenta donde se acumula lo recaudado.
        """
        ChartTemplate.try_loading('generic_coa', company)

        impuesto = ChartTemplate.ref('sale_tax_template', company)
        lineas = AccountTaxRepartitionLine.objects.filter(tax=impuesto)
        assert lineas.count() == 4
        assert lineas.filter(document_type='invoice').count() == 2
        assert lineas.filter(document_type='refund').count() == 2

        recibido = ChartTemplate.ref('tax_received', company)
        de_impuesto = lineas.filter(repartition_type='tax', document_type='invoice')
        assert de_impuesto.get().account == recibido

    def test_la_empresa_queda_con_sus_impuestos_por_defecto(self, company):
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
class TestPlantillaBase:
    """Los diarios no pertenecen a un plan: pertenecen a *tener* contabilidad.

    Se declaran con ``@template(model=...)`` sin código, y el resolutor los
    aplica a todo plan — ``[None] + parents`` en la referencia.
    """

    def test_la_empresa_recibe_los_seis_diarios(self, company):
        ChartTemplate.try_loading('generic_coa', company)

        diarios = AccountJournal.objects.filter(company=company)
        assert diarios.count() == 6
        assert set(diarios.values_list('code', flat=True)) == {
            'INV', 'BILL', 'MISC', 'EXCH', 'CABA', 'BNK1'}

    def test_el_diario_de_ventas_es_el_que_busca_el_asiento(self, company):
        """``create_invoice_from_subscription`` busca por ``type='sale'``.

        Es el consumidor real: sin un diario de ese tipo lanza ``UserError`` y
        el cobro no se puede asentar.
        """
        ChartTemplate.try_loading('generic_coa', company)

        venta = AccountJournal.objects.get(company=company, type='sale')
        assert venta.code == 'INV'
        assert venta == ChartTemplate.ref('sale', company)


@pytest.mark.django_db
class TestCargaAlCrearLaEmpresa:
    """El cargador sin consumidor no vale: una empresa hija hereda el plan.

    ≙ el ``create`` de la referencia, que instancia el plan de la raíz. Una
    empresa **raíz** no entra por aquí — su plan lo elige quien la aprovisiona.
    """

    def test_la_hija_hereda_el_plan_de_su_raiz(self, company):
        company.chart_template = 'generic_coa'
        company.save(update_fields=['chart_template'])

        hija = ResCompany.objects.create(
            code='acme-mx', name='ACME México', parent=company)

        assert AccountAccount.objects.filter(company=hija).count() == 46
        assert AccountJournal.objects.filter(company=hija, type='sale').exists()

    def test_sin_plan_en_la_raiz_no_se_carga_nada(self, company):
        """El receptor es no-op mientras nadie declare un plan.

        Es lo que hace que cablearlo no cambie el comportamiento de ninguna
        empresa existente.
        """
        assert company.chart_template is None

        hija = ResCompany.objects.create(
            code='acme-co', name='ACME Colombia', parent=company)

        assert AccountAccount.objects.filter(company=hija).count() == 0

    def test_la_raiz_no_se_carga_a_si_misma(self, db):
        """Una raíz es su propio ``parent_ids[0]`` — sin el guard se cargaría sola."""
        raiz = ResCompany.objects.create(
            code='beta-root', name='BETA', chart_template='generic_coa')

        assert AccountAccount.objects.filter(company=raiz).count() == 0


@pytest.mark.django_db
class TestAislamientoEntreEmpresas:
    def test_dos_empresas_tienen_planes_independientes(self, company):
        """``receivable`` no nombra una cuenta: nombra un papel.

        La cuenta concreta es la de cada empresa, y por eso el identificador
        externo lleva su id delante.
        """
        otra = ResCompany.objects.create(code='beta', name='BETA')
        ChartTemplate.try_loading('generic_coa', company)
        ChartTemplate.try_loading('generic_coa', otra)

        una = ChartTemplate.ref('receivable', company)
        dos = ChartTemplate.ref('receivable', otra)
        assert una != dos
        assert una.code == dos.code == '1210'
        assert una.company == company and dos.company == otra

    def test_recargar_no_duplica(self, company):
        """Idempotente por identificador externo, como la referencia."""
        ChartTemplate.try_loading('generic_coa', company)
        ChartTemplate.try_loading('generic_coa', company)

        assert AccountAccount.objects.filter(company=company).count() == 46
