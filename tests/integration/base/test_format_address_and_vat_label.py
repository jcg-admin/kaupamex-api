"""Tests — la decisión de los dos mixins de formato, sin arch XML de por medio.

Contrato adaptado de ``odoo19c: odoo/addons/base/models/res_partner.py:45-58``
(``FormatVatLabelMixin``) y ``:61-136`` (``FormatAddressMixin``).

Los dos mixins **deciden** algo y luego lo escriben en un árbol XML: qué
etiqueta lleva el campo fiscal, y en qué orden van ``zip`` / ``city`` /
``state``. Aquí se porta la decisión y diverge el destino — la misma forma que
``res_currency._get_view`` (``:726``) ya estableció en este árbol.

Qué haría fallar a cada control se declara en cada caso.
"""
import pytest

from addons.base.models import ResCompany, ResCountry, ResPartner
from addons.base.models.res_partner import (
    FormatAddressMixin,
    FormatVatLabelMixin,
)
from orm.environments import company_scope, context_scope

pytestmark = pytest.mark.integration


def _country(code, **extra):
    country, _created = ResCountry.objects.get_or_create(
        code=code, defaults={'name': f'País {code}', **extra})
    for key, value in extra.items():
        if getattr(country, key) != value:
            setattr(country, key, value)
            country.save()
    return country


@pytest.fixture
def company_in(db):
    """Una empresa cuyo país declara lo que el caso necesita medir."""
    def build(code, **country_fields):
        country = _country(code, **country_fields)
        partner = ResPartner.objects.create(name=f'Titular {code}',
                                            country=country)
        return ResCompany.objects.create(code=f'fmt-{code.lower()}',
                                         name=f'Empresa {code}',
                                         partner=partner)
    return build


class TestTheVatLabelReachesItsField:
    """≙ ``FormatVatLabelMixin._get_view`` (``:49-57``).

    La fuente escribe ``vat_label`` en el ``<field name="vat">`` **y** en su
    ``<label for="vat">``. Son dos nodos y un solo valor: el segundo existe
    porque *"in some module vat field is replaced"*, no porque la decisión sea
    distinta.
    """

    def test_the_field_that_takes_the_label_is_named(self, company_in):
        """El eje: la decisión no es sólo *cuál* etiqueta, es *qué campo* la
        lleva.

        Qué lo haría fallar: devolver la cadena suelta. ``vat_label_for`` ya
        la calcula; sin este método nadie sabe que su destino es ``vat``, y
        el serializer tendría que adivinarlo.
        """
        company = company_in('MX', vat_label='RFC')
        with company_scope(company.pk):
            assert FormatVatLabelMixin._get_view() == {'vat': 'RFC'}

    def test_a_country_without_label_touches_nothing(self, company_in):
        """CONTROL del ``if vat_label :=`` de la fuente (``:51``).

        Qué lo haría fallar: devolver ``{'vat': ''}``. Quien consuma el mapa
        rotularía el campo con la cadena vacía en vez de dejar el rótulo por
        defecto, que es lo que la fuente hace al no entrar en el ``if``.
        """
        company = company_in('SV', vat_label='')
        with company_scope(company.pk):
            assert FormatVatLabelMixin._get_view() == {}

    def test_without_a_company_in_context_it_touches_nothing(self, db):
        """CONTROL de la precondición: la fuente lee ``self.env.company``.

        Qué lo haría fallar: reventar con ``AttributeError`` sobre ``None``.
        """
        assert FormatVatLabelMixin._get_view() == {}

    def test_it_does_not_filter_by_view_type(self, company_in):
        """CONTROL que lo separa del mixin de dirección.

        ``FormatVatLabelMixin._get_view`` **no** tiene guarda de tipo de
        vista; ``FormatAddressMixin._get_view`` sí (``:133``). Copiar la
        guarda de uno al otro dejaría el rótulo fiscal fuera de la lista, que
        es donde la fuente sí lo pone.
        """
        company = company_in('ES', vat_label='NIF')
        with company_scope(company.pk):
            assert FormatVatLabelMixin._get_view(view_type='list') == {
                'vat': 'NIF'}


class TestTheAddressFieldOrder:
    """≙ la rama de ``address_format`` de ``_view_get_address``
    (``:96-125``), que es ordenar una lista."""

    def test_the_default_format_puts_city_state_and_zip_in_that_order(self, db):
        """El eje, con la plantilla por defecto de la fuente
        (``odoo19c: res_country.py:52``): ``%(city)s %(state_code)s %(zip)s``.
        """
        country = _country(
            'DF',
            address_format='%(street)s\n%(city)s %(state_code)s %(zip)s')
        assert FormatAddressMixin.field_order_for(country) == [
            'city', 'state_id', 'zip']

    def test_the_fields_the_format_omits_go_at_the_end(self, db):
        """El control que separa el orden COMPLETO del orden declarado.

        La fuente arranca de ``concerned_fields = {'zip','city','state_id'}``
        y, tras recorrer el formato, **añade lo que sobra al final**
        (``:119-124``). Un formato que sólo nombra ``zip`` y ``city`` sigue
        teniendo que colocar ``state_id`` en alguna parte.

        Qué lo haría fallar: devolver la línea del formato tal cual. Ése era
        exactamente el alcance de ``field_order_for`` antes de este porte —
        media conducta, y la mitad ausente no se veía.
        """
        country = _country('PT', address_format='%(street)s\n%(zip)s %(city)s')
        assert FormatAddressMixin.field_order_for(country) == [
            'zip', 'city', 'state_id']

    def test_state_name_maps_to_the_same_field_as_state_code(self, db):
        """``:112-113`` — los dos derivados apuntan al mismo campo real."""
        country = _country('IT',
                           address_format='%(city)s %(state_name)s %(zip)s')
        assert FormatAddressMixin.field_order_for(country) == [
            'city', 'state_id', 'zip']

    def test_naming_both_derivatives_does_not_duplicate_the_field(self, db):
        """CONTROL del mapeo: un nodo XML no puede estar en dos sitios.

        Qué lo haría fallar: emitir ``state_id`` dos veces. Quien pinte la
        dirección dibujaría el estado dos veces.
        """
        country = _country(
            'CH', address_format='%(city)s %(state_code)s %(state_name)s')
        order = FormatAddressMixin.field_order_for(country)
        assert order.count('state_id') == 1

    def test_a_field_outside_the_three_keeps_its_place(self, db):
        """``:114-118`` mueve **todo** campo de la línea, no sólo los tres.

        Qué lo haría fallar: filtrar a ``{zip, city, state_id}``. El país que
        pone el nombre del país en la misma línea vería su orden roto.
        """
        country = _country(
            'BR', address_format='%(city)s %(country_name)s %(zip)s')
        assert FormatAddressMixin.field_order_for(country) == [
            'city', 'country_name', 'zip', 'state_id']

    def test_a_format_with_no_city_line_orders_nothing(self, db):
        """``:105-106`` — sin línea de ciudad, la fuente no reordena."""
        country = _country('AQ', address_format='%(street)s\n%(country_name)s')
        assert FormatAddressMixin.field_order_for(country) == []


class TestTheAddressViewDecision:
    """≙ ``FormatAddressMixin._get_view`` (``:130-135``) y
    ``_get_view_cache_key`` (``:127-129``)."""

    def test_the_form_view_carries_the_order(self, company_in):
        company = company_in('MX', address_format='%(zip)s %(city)s')
        with company_scope(company.pk):
            assert FormatAddressMixin._get_view() == {
                'address_field_order': ['zip', 'city', 'state_id']}

    def test_a_view_that_is_not_a_form_gets_no_order(self, company_in):
        """``:133`` — ``if view.type == 'form'``.

        Qué lo haría fallar: reordenar también la lista. Es la asimetría que
        la fuente declara, y la que separa a este mixin del fiscal.
        """
        company = company_in('MX', address_format='%(zip)s %(city)s')
        with company_scope(company.pk):
            assert FormatAddressMixin._get_view(view_type='list') == {}

    def test_the_context_flag_disables_the_reordering(self, company_in):
        """``:96`` — ``not self.env.context.get('no_address_format')``.

        La fuente la usa para no reformatear una dirección **dentro** de otra
        ya formateada. Qué lo haría fallar: ignorar la clave y reordenar
        igual, que es el bucle que la bandera existe para cortar.
        """
        company = company_in('MX', address_format='%(zip)s %(city)s')
        with company_scope(company.pk), context_scope(no_address_format=True):
            assert FormatAddressMixin._get_view() == {}

    def test_the_cache_key_varies_with_the_company(self, company_in):
        """``:127-129``, verbatim: *"Different companies could use each a
        different address view"*.

        Qué lo haría fallar: una llave que ignore la empresa. Dos empresas con
        formatos distintos compartirían un orden que contradice a una de las
        dos.
        """
        one = company_in('MX', address_format='%(zip)s %(city)s')
        other = company_in('PE', address_format='%(city)s %(zip)s')
        with company_scope(one.pk):
            first = FormatAddressMixin._get_view_cache_key()
        with company_scope(other.pk):
            second = FormatAddressMixin._get_view_cache_key()
        assert first != second

    def test_the_cache_key_varies_with_the_context_flag(self, company_in):
        """La segunda mitad de ``:129`` — la llave lleva la bandera.

        Qué lo haría fallar: dejarla fuera. La misma empresa serviría el
        orden cacheado a la llamada que pidió no formatear.
        """
        company = company_in('MX', address_format='%(zip)s %(city)s')
        with company_scope(company.pk):
            plain = FormatAddressMixin._get_view_cache_key()
            with context_scope(no_address_format=True):
                flagged = FormatAddressMixin._get_view_cache_key()
        assert plain != flagged

    def test_the_same_company_gives_the_same_key(self, company_in):
        """El control positivo: sin él, una llave con un valor al azar
        también pasaría los dos casos anteriores y no cachearía nada."""
        company = company_in('MX', address_format='%(zip)s %(city)s')
        with company_scope(company.pk):
            assert (FormatAddressMixin._get_view_cache_key()
                    == FormatAddressMixin._get_view_cache_key())
