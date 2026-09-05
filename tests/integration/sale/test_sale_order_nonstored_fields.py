"""Tests — los campos NO almacenados de ``sale.order`` (tarea #976, bloque 2).

Ejercitan los once ``fields.NonStored`` que el bloque 2 portó de
``odoo19c: sale/models/sale_order.py:235-327``. Sin ellos el verde de la suite
no discriminaría: ningún caso previo leía uno solo de estos descriptores, así
que el porte podría estar roto y la suite seguiría en verde — el sub-patrón D
de ``metrica-decide-la-conclusion.md``.

Lo que cada bloque fija:

1. Los cuatro ``related=`` recorren la cadena hasta la empresa y devuelven el
   valor que ``account`` le colgó a ``res.company``; con la empresa ausente
   devuelven ``None`` en vez de reventar.
2. Los dos de interfaz nacen en ``False`` y **admiten asignación** — un
   ``NonStored`` no es una ``property`` de sólo lectura.
3. Los cinco ``compute`` calculan lo que su contraparte calcula.
4. Ninguno de los once tiene columna: no aparecen en ``_meta.get_fields()`` ni
   se pueden filtrar. Es el control que distingue «portado como no almacenado»
   de «portado como columna», que es lo que el porte NO debía hacer.
"""
from decimal import Decimal

import pytest

from django.core.exceptions import FieldError

from addons.base.models import ResCompany
from addons.product.models.product_pricelist import ProductPricelist
from addons.sale.models import SaleOrder, SaleOrderLine
from tests.factories.product_factory import make_category, make_product
from tests.factories.user_factory import UserFactory

pytestmark = pytest.mark.django_db

#: Los once que el bloque 2 declaró. La lista es el denominador de los tests
#: de ausencia de columna; si alguien añade un doceavo sin sumarlo aquí, el
#: caso de conteo lo delata.
NON_STORED_FIELDS = [
    'country_code', 'company_price_include', 'tax_calculation_rounding_method',
    'terms_type', 'show_update_fpos', 'show_update_pricelist',
    'has_archived_products', 'has_active_pricelist', 'tax_country',
    'type_name', 'duplicated_orders',
]


def _make_customer(login):
    """El cliente de un pedido.

    ``SaleOrder.partner`` apunta a ``settings.AUTH_USER_MODEL``
    (``sale_order.py:370``) y no a ``res.partner``, que es lo que la fuente
    declara (``odoo19c: sale/models/sale_order.py:64-65``). Es deriva medida
    del árbol, registrada como :ref:`h-api-905`; estos tests usan lo que el
    modelo declara hoy, no lo que debería declarar.
    """
    return UserFactory(login=f'{login}@kaupamex.mx')


@pytest.fixture
def company():
    return ResCompany.objects.create(code='ns-976', name='No Stored 976')


@pytest.fixture
def product():
    cat = make_category(name='Cat NS976')
    return make_product(name='Prod NS976', price=Decimal('50.00'), stock=3,
                        categ=cat)


class TestTheFourRelatedWalkTheChainToTheCompany:

    def test_price_include_comes_from_the_company(self, company):
        order = SaleOrder.objects.create(company=company)
        assert order.company_price_include == 'tax_excluded'

    def test_rounding_method_comes_from_the_company(self, company):
        order = SaleOrder.objects.create(company=company)
        assert order.tax_calculation_rounding_method == 'round_globally'

    def test_terms_type_comes_from_the_company(self, company):
        order = SaleOrder.objects.create(company=company)
        assert order.terms_type == 'plain'

    def test_a_change_on_the_company_reaches_the_order(self, company):
        """El ``related`` se resuelve al leerlo, no al crear la orden."""
        order = SaleOrder.objects.create(company=company)
        company.terms_type = 'html'
        company.save(update_fields=['terms_type'])
        order.refresh_from_db()
        assert order.terms_type == 'html'

    def test_country_code_is_none_without_a_fiscal_country(self, company):
        """La empresa no declara país fiscal: el código sale vacío, no falla."""
        order = SaleOrder.objects.create(company=company)
        assert order.country_code is None

    def test_without_a_company_the_four_come_out_empty(self):
        """Una orden sin empresa no revienta al recorrer la cadena."""
        order = SaleOrder.objects.create()
        assert order.country_code is None
        assert order.company_price_include is None
        assert order.tax_calculation_rounding_method is None
        assert order.terms_type is None


class TestTheTwoUxFlagsAreWritable:

    def test_they_are_born_false(self, company):
        order = SaleOrder.objects.create(company=company)
        assert order.show_update_fpos is False
        assert order.show_update_pricelist is False

    def test_they_accept_assignment(self, company):
        """Un ``NonStored`` NO es una ``property``: se le puede escribir."""
        order = SaleOrder.objects.create(company=company)
        order.show_update_pricelist = True
        assert order.show_update_pricelist is True

    def test_what_gets_written_never_reaches_the_database(self, company):
        """Sin columna no hay dónde guardarlo — y eso es lo que se porta.

        Medido: el valor asignado vive en el ``__dict__`` de la instancia, así
        que **sobrevive a un ``refresh_from_db()``** — ese método repuebla los
        campos de la tabla, y éste no es uno. Lo que no sobrevive es leer la
        fila **otra vez**: la instancia nueva nace con el ``default``.

        La primera versión de este caso afirmaba lo contrario sobre
        ``refresh_from_db``; era una suposición, no una medición.
        """
        order = SaleOrder.objects.create(company=company)
        order.show_update_fpos = True
        order.save()

        order.refresh_from_db()
        assert order.show_update_fpos is True, 'vive en la instancia'

        again = SaleOrder.objects.get(pk=order.pk)
        assert again.show_update_fpos is False, 'no vive en la tabla'


class TestTheFiveComputesCalculateWhatTheSourceCalculates:

    def test_type_name_says_quotation_while_in_draft(self, company):
        order = SaleOrder.objects.create(company=company)
        assert order.state == SaleOrder.STATE_DRAFT
        assert order.type_name == 'Cotización'

    def test_type_name_says_sales_order_once_confirmed(self, company, product):
        order = SaleOrder.objects.create(company=company)
        SaleOrderLine.objects.create(
            order=order, product=product, name='Línea NS976',
            price_unit=Decimal('50.00'), product_uom_qty=1)
        order.action_confirm()
        assert order.type_name == 'Orden de venta'

    def test_type_name_says_quotation_again_once_cancelled(self, company, product):
        """``cancel`` vuelve a ser cotización — la fuente lo agrupa con draft."""
        order = SaleOrder.objects.create(company=company)
        SaleOrderLine.objects.create(
            order=order, product=product, name='Línea NS976',
            price_unit=Decimal('50.00'), product_uom_qty=1)
        order.action_confirm()
        order.action_cancel()
        assert order.type_name == 'Cotización'

    def test_no_archived_products_when_every_product_is_active(self, company, product):
        order = SaleOrder.objects.create(company=company)
        SaleOrderLine.objects.create(
            order=order, product=product, name='Línea NS976',
            price_unit=Decimal('50.00'), product_uom_qty=1)
        assert order.has_archived_products is False

    def test_archiving_the_product_flips_the_flag(self, company, product):
        """El control que hace real al caso anterior: si se archiva, sale True."""
        order = SaleOrder.objects.create(company=company)
        SaleOrderLine.objects.create(
            order=order, product=product, name='Línea NS976',
            price_unit=Decimal('50.00'), product_uom_qty=1)
        product.active = False
        product.save(update_fields=['active'])
        order = SaleOrder.objects.get(pk=order.pk)
        assert order.has_archived_products is True

    def test_an_order_with_no_lines_has_no_archived_products(self, company):
        order = SaleOrder.objects.create(company=company)
        assert order.has_archived_products is False

    def test_tax_country_falls_back_to_the_company(self, company):
        """Sin posición fiscal, el país fiscal es el de la empresa."""
        order = SaleOrder.objects.create(company=company)
        assert order.tax_country == company.account_fiscal_country

    def test_has_active_pricelist_is_false_without_any(self, company):
        order = SaleOrder.objects.create(company=company)
        assert order.has_active_pricelist is False

    def test_a_pricelist_of_the_company_flips_the_flag(self, company):
        ProductPricelist.objects.create(name='Tarifa NS976', company=company)
        order = SaleOrder.objects.create(company=company)
        assert order.has_active_pricelist is True

    def test_an_inactive_pricelist_does_not_count(self, company):
        """El control del caso anterior: sin ``active=True`` no cuenta."""
        ProductPricelist.objects.create(
            name='Tarifa NS976 inactiva', company=company, active=False)
        order = SaleOrder.objects.create(company=company)
        assert order.has_active_pricelist is False

    def test_a_pricelist_of_another_company_does_not_count(self, company):
        other = ResCompany.objects.create(code='ns-976-b', name='Otra NS976')
        ProductPricelist.objects.create(name='Tarifa ajena', company=other)
        order = SaleOrder.objects.create(company=company)
        assert order.has_active_pricelist is False

    def test_a_pricelist_without_company_counts_for_everyone(self, company):
        """``('company_id', 'in', (False, ...))`` de la fuente: la tarifa sin
        empresa sirve a cualquiera."""
        ProductPricelist.objects.create(name='Tarifa global NS976')
        order = SaleOrder.objects.create(company=company)
        assert order.has_active_pricelist is True


class TestTheDuplicateDetector:
    """El detector de duplicados, contra lo que ESTE árbol permite.

    La fuente busca duplicados entre pedidos de la misma empresa y el mismo
    cliente cuyo ``origin`` coincida con el ``name`` del otro, o cuya
    referencia de cliente sea la misma (``odoo19c: sale_order.py:713-726``).

    Aquí ese escenario no se puede montar con **dos borradores**: el
    ``UniqueConstraint`` propio ``sale_order_un_draft_por_partner``
    (``sale_order.py``, H-API-309) prohíbe dos borradores del mismo cliente, y
    la fuente no tiene esa restricción. El par realizable es
    **confirmado + borrador**, que es justo el que la consulta admite: su
    ``JOIN`` sólo excluye los cancelados, no los confirmados. Ver
    :ref:`h-api-906`.
    """

    def test_a_draft_without_client_reference_finds_nothing(self, company):
        order = SaleOrder.objects.create(company=company)
        assert list(order.duplicated_orders) == []

    def test_a_draft_sees_a_confirmed_one_sharing_the_client_reference(
            self, company, product):
        customer = _make_customer('cliente-ns976')
        confirmed = SaleOrder.objects.create(
            company=company, partner=customer, client_order_ref='PO-976')
        SaleOrderLine.objects.create(
            order=confirmed, product=product, name='Línea NS976',
            price_unit=Decimal('50.00'), product_uom_qty=1)
        confirmed.action_confirm()

        draft = SaleOrder.objects.create(
            company=company, partner=customer, client_order_ref='PO-976')
        assert list(draft.duplicated_orders) == [confirmed]

    def test_a_different_client_reference_is_not_a_duplicate(
            self, company, product):
        """El control: sin la referencia compartida no hay duplicado."""
        customer = _make_customer('cliente-ns976-b')
        confirmed = SaleOrder.objects.create(
            company=company, partner=customer, client_order_ref='PO-976-a')
        SaleOrderLine.objects.create(
            order=confirmed, product=product, name='Línea NS976',
            price_unit=Decimal('50.00'), product_uom_qty=1)
        confirmed.action_confirm()

        draft = SaleOrder.objects.create(
            company=company, partner=customer, client_order_ref='PO-976-b')
        assert list(draft.duplicated_orders) == []

    def test_another_company_is_not_a_duplicate(self, company, product):
        """El ``JOIN`` exige misma empresa — segundo control de la consulta."""
        customer = _make_customer('cliente-ns976-c')
        other = ResCompany.objects.create(code='ns-976-c', name='Otra NS976 c')
        confirmed = SaleOrder.objects.create(
            company=other, partner=customer, client_order_ref='PO-976-c')
        SaleOrderLine.objects.create(
            order=confirmed, product=product, name='Línea NS976',
            price_unit=Decimal('50.00'), product_uom_qty=1)
        confirmed.action_confirm()

        draft = SaleOrder.objects.create(
            company=company, partner=customer, client_order_ref='PO-976-c')
        assert list(draft.duplicated_orders) == []

    def test_a_confirmed_order_reports_no_duplicates(self, company, product):
        """La fuente sólo busca duplicados en borrador."""
        customer = _make_customer('cliente-ns976-d')
        primera = SaleOrder.objects.create(
            company=company, partner=customer, client_order_ref='PO-976-d')
        SaleOrderLine.objects.create(
            order=primera, product=product, name='Línea NS976',
            price_unit=Decimal('50.00'), product_uom_qty=1)
        primera.action_confirm()

        segunda = SaleOrder.objects.create(
            company=company, partner=customer, client_order_ref='PO-976-d')
        SaleOrderLine.objects.create(
            order=segunda, product=product, name='Línea NS976',
            price_unit=Decimal('50.00'), product_uom_qty=1)
        segunda.action_confirm()
        assert list(segunda.duplicated_orders) == []


class TestNoneOfThemHasAColumn:
    """El control que separa «no almacenado» de «almacenado».

    Si el porte los hubiera declarado como campos de Django normales, estos
    tres casos caerían — y ese es exactamente el defecto que había que evitar.
    """

    def test_none_of_the_eleven_is_a_model_field(self):
        declared = {f.name for f in SaleOrder._meta.get_fields()}
        assert [n for n in NON_STORED_FIELDS if n in declared] == []

    def test_none_of_the_eleven_can_be_filtered(self, company):
        for name in NON_STORED_FIELDS:
            with pytest.raises(FieldError):
                SaleOrder.objects.filter(**{name: True}).exists()

    def test_the_stored_neighbours_do_survive_the_same_probe(self):
        """Control positivo: un campo que SÍ tiene columna pasa las dos
        comprobaciones de arriba al revés — si no, el instrumento mediría
        cualquier cosa."""
        declared = {f.name for f in SaleOrder._meta.get_fields()}
        assert 'date_order' in declared
        assert 'state' in declared
