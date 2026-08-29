"""``sale`` amplía el mapa de cuentas de propiedad — tarea #976.

Tres cosas distintas, separadas porque fallan por causas distintas:

1. que el registro de ajustes exista y ``sale`` esté inscrito en él;
2. que el mapa resultante lleve la entrada de la cuenta de anticipo **además**
   de las tres que ``account`` declara;
3. que el llamador siembre el ``ir.default`` — sin él el mapa es un método
   correcto al que nadie llama (:ref:`h-api-346`).

*Metrica:* el dict que ``_get_property_accounts`` devuelve y las filas de
``ir.default`` que ``set_property_account_defaults`` escribe contra PostgreSQL
real.
*Ciega a:* que la carga completa de un plan pase por aquí — estos casos llaman
al método directamente. Que ``load()`` lo invoque lo mide su propia cadena, no
un caso de este archivo.
"""
import pytest

from addons.account.models.chart_template import (
    PROPERTY_ACCOUNTS_OVERRIDES, ChartTemplate, property_accounts_override,
)
from addons.account.models.account_account import AccountAccount
from addons.base.models.ir_default import IrDefault
from addons.base.models.ir_model import IrModelData
from addons.base.models import ResCompany
from addons.sale.models.chart_template import add_downpayment_account

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture
def company():
    return ResCompany.objects.create(code='acme', name='ACME')


@pytest.fixture
def receivable(company):
    return AccountAccount.objects.create(
        code='11100', name='Clientes', account_type='asset_receivable',
        company=company)


class TestTheOverrideIsRegistered:
    """≙ ``_inherit = 'account.chart.template'`` (``odoo19c: :4``)."""

    def test_sale_is_in_the_registry(self):
        assert add_downpayment_account in PROPERTY_ACCOUNTS_OVERRIDES

    def test_registering_twice_leaves_it_once(self):
        """El decorador es idempotente: ``ready()`` puede correr dos veces.

        Se restaura el registro al salir. ``PROPERTY_ACCOUNTS_OVERRIDES`` es
        una lista de módulo: lo que este caso inscriba sobrevive a su propia
        transacción y llega a los casos siguientes, que entonces pasarían por
        el estado que éste dejó y no por lo que ``sale`` declara. Lo destapó
        el mutante de ``mutante_sin_extension.py``.
        """
        before = list(PROPERTY_ACCOUNTS_OVERRIDES)
        try:
            property_accounts_override(add_downpayment_account)
            assert PROPERTY_ACCOUNTS_OVERRIDES.count(add_downpayment_account) == 1
        finally:
            PROPERTY_ACCOUNTS_OVERRIDES[:] = before


class TestTheMap:

    def test_the_three_keys_account_declares(self):
        """≙ ``odoo19c: chart_template.py:802-807``."""
        mapping = ChartTemplate._get_property_accounts({})
        assert mapping['property_account_receivable_id'] == 'res.partner'
        assert mapping['property_account_payable_id'] == 'res.partner'
        assert mapping['property_stock_journal'] == 'product.category'

    def test_sale_adds_the_downpayment_account_to_the_company(self):
        """≙ ``property_accounts['downpayment_account_id'] = 'res.company'``.

        La clave lleva el nombre de NUESTRO campo (``downpayment_account``,
        forma A congelada en #143), no el de la fuente: el consumidor la busca
        en ``_meta`` y con el nombre ajeno la descartaría en silencio.
        """
        mapping = ChartTemplate._get_property_accounts({})
        assert mapping['downpayment_account'] == 'res.company'

    def test_without_the_override_the_key_is_absent(self):
        """Control: el mapa base NO trae la cuenta de anticipo.

        Si pasara con y sin ``sale`` inscrito, el caso de arriba no mediría la
        extensión — mediría que el diccionario tiene claves
        (``metrica-decide-la-conclusion``, sub-patrón D).
        """
        before = list(PROPERTY_ACCOUNTS_OVERRIDES)
        try:
            # ``remove`` a secas caería con ``ValueError`` si el símbolo no
            # estuviera inscrito — el control fallaría por la retirada y no
            # por su aserto, que es fallar por el motivo equivocado.
            PROPERTY_ACCOUNTS_OVERRIDES[:] = [
                f for f in before if f is not add_downpayment_account]
            assert 'downpayment_account' not in ChartTemplate._get_property_accounts({})
        finally:
            PROPERTY_ACCOUNTS_OVERRIDES[:] = before

    def test_additional_properties_come_through(self):
        """≙ el ``**additional_properties`` de la fuente (``:804``)."""
        mapping = ChartTemplate._get_property_accounts({'property_x': 'res.partner'})
        assert mapping['property_x'] == 'res.partner'

    def test_the_public_name_is_gone(self):
        """El guion bajo es el contrato (H-API-581)."""
        assert not hasattr(ChartTemplate, 'get_property_accounts')


class TestTheDefaultsAreSeeded:
    """≙ el bucle de ``ir.default`` (``odoo19c: chart_template.py:766-783``)."""

    def test_a_declared_property_becomes_an_ir_default(self, company, receivable):
        # El identificador es POR EMPRESA — ≙ ``company_xmlid`` (``:285``):
        # ``receivable`` nombra el papel, no la cuenta.
        IrModelData.objects.create(
            module='account', name=f'{company.pk}_receivable_test',
            model='account.AccountAccount', res_id=receivable.pk)
        ChartTemplate.set_property_account_defaults(
            company, {'property_account_receivable_id': 'receivable_test'}, {})
        default = IrDefault.objects.get(
            model='res.partner', field='property_account_receivable_id',
            company=company)
        assert default.json_value == str(receivable.pk)

    def test_a_key_whose_model_lacks_the_field_is_skipped(self, company):
        """``property_stock_journal`` lo declara ``stock_account``, sin portar.

        ≙ la guarda ``field in self.env[model]._fields`` de la fuente: no
        aborta la carga del plan, se salta la entrada.
        """
        ChartTemplate.set_property_account_defaults(
            company, {'property_stock_journal': 'lo_que_sea'}, {})
        assert not IrDefault.objects.filter(field='property_stock_journal').exists()

    def test_the_company_income_account_seeds_the_product_category(
        self, company, receivable,
    ):
        """≙ ``:772-777`` — la cuenta sale de la empresa, no del plan."""
        company.income_account_id = receivable
        company.save(update_fields=['income_account_id'])
        ChartTemplate.set_property_account_defaults(company, {}, {})
        default = IrDefault.objects.get(
            model='product.category', field='property_account_income_categ',
            company=company)
        assert default.json_value == str(receivable.pk)

    def test_a_company_without_the_account_seeds_nothing(self, company):
        ChartTemplate.set_property_account_defaults(company, {}, {})
        assert not IrDefault.objects.filter(model='product.category').exists()
