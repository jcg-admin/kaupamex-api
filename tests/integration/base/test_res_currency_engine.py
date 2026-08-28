"""Tests — el motor de tipos de cambio de ``res.currency`` y su presentación.

Contrato adaptado de ``odoo19c: odoo/addons/base/models/res_currency.py``,
clase ``ResCurrency`` (``:20-343``).

Estos veinte símbolos estaban declarados «sin consumidor» o «bloqueados». La
premisa cayó al portarse ``res.currency.rate``; los casos de abajo son lo que
hace observable que el motor funciona.

**Qué haría fallar a cada control se declara en su caso.**
"""
from datetime import date
from decimal import Decimal

import pytest
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import connection

from addons.base.models import (IrModelData, ResCompany, ResCurrency,
                                ResGroups, res_currency)
from addons.base.models.res_currency import ResCurrencyRate
from orm.environments import company_scope, context_scope

pytestmark = pytest.mark.integration


@pytest.fixture
def mxn(db):
    return ResCurrency.objects.create(name='XMX', symbol='$', rounding='0.01',
                                      currency_unit_label='Pesos',
                                      currency_subunit_label='Centavos')


@pytest.fixture
def usd(db):
    return ResCurrency.objects.create(name='XUS', symbol='US$',
                                      rounding='0.01')


@pytest.fixture
def company(db, mxn):
    return ResCompany.objects.create(code='cur-co', name='Cur Co',
                                     currency=mxn)


def _rate(currency, day, value, company=None):
    return ResCurrencyRate.objects.create(
        currency=currency, company=company, name=day, rate=Decimal(str(value)))


class TestDecimalPlaces:
    """≙ ``_compute_decimal_places`` (``odoo19c: res_currency.py:162-168``)."""

    @pytest.mark.parametrize('rounding,expected', [
        ('0.01', 2), ('0.001', 3), ('1', 0), ('0.05', 2), ('10', 0),
    ])
    def test_the_places_come_from_the_magnitude_not_the_factor(
            self, db, rounding, expected):
        """Qué haría fallar al control: contar los decimales del factor.

        ``0.05`` tiene dos decimales escritos y ``ceil(log10(1/0.05))`` da
        **2** también, pero por otra razón; ``1`` tiene cero escritos y da 0
        por la rama del ``else``. El caso de ``10`` es el que discrimina: su
        magnitud es mayor que 1, así que cae al 0 y no a un negativo.
        """
        currency = ResCurrency.objects.create(
            name=f'X{rounding[-1]}{expected}', symbol='x', rounding=rounding)
        assert currency.decimal_places == expected

    def test_it_is_computed_on_save_not_only_on_demand(self, db):
        """Qué haría fallar al control: no llamarlo desde ``save()``.

        El valor tiene que estar **en la columna**, porque lo leen
        ``round()``, ``format()`` y ``get_all_currencies``.
        """
        currency = ResCurrency.objects.create(name='XD3', symbol='x',
                                              rounding='0.001')
        currency.refresh_from_db()
        assert currency.decimal_places == 3


class TestGetRates:
    """≙ ``_get_rates`` (``odoo19c: res_currency.py:117-138``)."""

    def test_the_last_rate_up_to_the_date_wins(self, mxn, usd, company):
        """Qué haría fallar al control: tomar la última sin mirar la fecha.

        Hay una tasa posterior a la consultada. Con el filtro, gana la del 1
        de febrero; sin él, la del 1 de marzo.
        """
        _rate(usd, date(2026, 2, 1), 20, company)
        _rate(usd, date(2026, 3, 1), 25, company)
        rates = ResCurrency._get_rates([usd], company, date(2026, 2, 15))
        assert rates[usd.pk] == Decimal('20')

    def test_the_date_itself_counts(self, mxn, usd, company):
        """``name <= date``, no ``<``: la tasa de hoy rige hoy.

        Qué haría fallar al control: usar ``__lt``.
        """
        _rate(usd, date(2026, 2, 15), 20, company)
        rates = ResCurrency._get_rates([usd], company, date(2026, 2, 15))
        assert rates[usd.pk] == Decimal('20')

    def test_an_earlier_rate_is_the_fallback_when_none_precedes(
            self, mxn, usd, company):
        """El segundo escalón de la fuente, y el menos obvio.

        Qué haría fallar al control: caer a 1.0 en cuanto no haya tasa
        anterior. Con esa lectura, un asiento fechado antes de la primera
        tasa saldría **sin convertir**; con el escalón, se convierte con la
        primera que existe.
        """
        _rate(usd, date(2026, 3, 1), 25, company)
        rates = ResCurrency._get_rates([usd], company, date(2026, 1, 1))
        assert rates[usd.pk] == Decimal('25')

    def test_without_any_rate_the_currency_measures_one(self, usd, company):
        """El tercer escalón."""
        rates = ResCurrency._get_rates([usd], company, date(2026, 1, 1))
        assert rates[usd.pk] == Decimal('1.0')

    def test_the_company_rate_beats_the_global_one(self, mxn, usd, company):
        """Qué haría fallar al control: ordenar los nulos primero.

        La tasa propia de la empresa y la global tienen la MISMA fecha, así
        que sólo el orden por empresa las separa. Con los nulos al final gana
        la propia (30); con los nulos primero, la global (20).
        """
        _rate(usd, date(2026, 2, 1), 20, None)
        _rate(usd, date(2026, 2, 1), 30, company)
        rates = ResCurrency._get_rates([usd], company, date(2026, 2, 15))
        assert rates[usd.pk] == Decimal('30')

    def test_the_global_rate_applies_when_there_is_no_company_one(
            self, mxn, usd, company):
        """El control positivo del caso anterior: sin él, un filtro que
        excluyera la global también lo pasaría."""
        _rate(usd, date(2026, 2, 1), 20, None)
        rates = ResCurrency._get_rates([usd], company, date(2026, 2, 15))
        assert rates[usd.pk] == Decimal('20')

    def test_an_empty_list_asks_nothing(self, company):
        assert ResCurrency._get_rates([], company, date(2026, 1, 1)) == {}


class TestConversion:
    """≙ ``_get_conversion_rate`` (``:271-281``) y ``_convert`` (``:283-302``)."""

    def test_the_same_currency_converts_exactly(self, mxn, company):
        """Qué haría fallar al control: quitar el corto-circuito.

        No es optimización: sin él, un importe pasa por una división y una
        multiplicación, y el redondeo de ida y vuelta puede moverlo.
        """
        assert ResCurrency._get_conversion_rate(mxn, mxn, company) == Decimal('1')

    def test_converting_multiplies_by_the_ratio_of_the_two_rates(
            self, mxn, usd, company):
        """La moneda de la empresa vale 1 y el dólar 20, así que 5 dólares
        son 100 pesos.

        Qué haría fallar al control: invertir el cociente. Con la inversión
        darían 0.25, que es un valor distinto — el caso discrimina.
        """
        _rate(mxn, date(2026, 1, 1), 1, company)
        _rate(usd, date(2026, 1, 1), Decimal('0.05'), company)
        converted = usd._convert(Decimal('5'), mxn, company, date(2026, 2, 1))
        assert converted == Decimal('100.00')

    def test_a_zero_amount_short_circuits(self, mxn, usd, company):
        """La fuente devuelve 0 **sin consultar tasa alguna**.

        Qué haría fallar al control: consultar igual. Aquí no hay ninguna
        tasa sembrada, así que una consulta caería al 1.0 y daría 0 también —
        por eso el caso mide el tipo: la fuente devuelve el cero de la moneda,
        no ``None``.
        """
        assert usd._convert(Decimal('0'), mxn, company) == Decimal('0')

    def test_the_result_is_rounded_with_the_target_currency(
            self, mxn, company):
        """Qué haría fallar al control: redondear con la moneda de origen.

        El origen tiene tres decimales y el destino dos. Un importe que en el
        origen conservaría el tercer decimal tiene que perderlo al llegar.
        """
        centimo = ResCurrency.objects.create(name='XML', symbol='m',
                                             rounding='0.001')
        _rate(mxn, date(2026, 1, 1), 1, company)
        _rate(centimo, date(2026, 1, 1), 1, company)
        converted = centimo._convert(Decimal('1.005'), mxn, company,
                                     date(2026, 2, 1))
        assert converted == Decimal('1.01')

    def test_round_false_keeps_the_full_precision(self, mxn, company):
        """El control negativo del anterior: sin él, un ``round`` que
        ignorara su parámetro pasaría igual."""
        centimo = ResCurrency.objects.create(name='XM2', symbol='m',
                                             rounding='0.001')
        _rate(mxn, date(2026, 1, 1), 1, company)
        _rate(centimo, date(2026, 1, 1), 1, company)
        converted = centimo._convert(Decimal('1.005'), mxn, company,
                                     date(2026, 2, 1), round=False)
        assert converted == Decimal('1.005')


class TestCurrentRate:
    """≙ ``_compute_current_rate`` (``odoo19c: res_currency.py:145-159``)."""

    def test_the_company_currency_gets_no_label(self, mxn, company):
        """``rate_string`` es ``''`` para la moneda de la propia empresa.

        Qué haría fallar al control: rotular siempre. «1 XMX = 1.000000 XMX»
        no informa de nada y ocupa la columna.
        """
        _rate(mxn, date(2026, 1, 1), 1, company)
        with company_scope(company.pk):
            assert mxn._compute_current_rate(company=company)[2] == ''

    def test_another_currency_gets_a_label_naming_both(
            self, mxn, usd, company):
        """El control positivo: sin él, un ``rate_string`` vacío siempre
        pasaría el caso anterior."""
        _rate(mxn, date(2026, 1, 1), 1, company)
        _rate(usd, date(2026, 1, 1), Decimal('0.05'), company)
        with company_scope(company.pk):
            label = usd._compute_current_rate(company=company)[2]
        assert mxn.name in label and usd.name in label

    def test_the_two_rates_are_reciprocal(self, mxn, usd, company):
        """Qué haría fallar al control: devolver la misma en las dos
        posiciones."""
        _rate(mxn, date(2026, 1, 1), 1, company)
        _rate(usd, date(2026, 1, 1), Decimal('0.05'), company)
        with company_scope(company.pk):
            rate, inverse, _label = usd._compute_current_rate(company=company)
        assert rate == Decimal('0.05')
        assert inverse == Decimal('20')

    def test_the_properties_expose_the_three(self, mxn, usd, company):
        """Las tres properties son los nombres públicos de la fuente."""
        _rate(mxn, date(2026, 1, 1), 1, company)
        _rate(usd, date(2026, 1, 1), Decimal('0.05'), company)
        with company_scope(company.pk):
            assert usd.rate == Decimal('0.05')
            assert usd.inverse_rate == Decimal('20')
            assert usd.rate_string


class TestDateAndCompanyCurrency:
    """≙ ``_compute_date`` (``:170-173``) y
    ``_compute_is_current_company_currency`` (``:142-145``)."""

    def test_the_date_is_the_newest_rate(self, usd, company):
        """Qué haría fallar al control: tomar la más antigua.

        ``rate_ids`` sale ordenado por el ``_order`` de la tasa
        (``name desc``), así que ``[:1]`` es la más reciente — y este caso lo
        mide en vez de asumirlo.
        """
        _rate(usd, date(2026, 1, 1), 20, company)
        _rate(usd, date(2026, 3, 1), 25, company)
        assert usd.date == date(2026, 3, 1)

    def test_without_rates_there_is_no_date(self, usd):
        assert usd.date is None

    def test_the_company_currency_knows_it_is(self, mxn, usd, company):
        """Qué haría fallar al control: devolver ``True`` siempre.

        Por eso el caso mide las dos monedas, no una.
        """
        with company_scope(company.pk):
            assert mxn.is_current_company_currency is True
            assert usd.is_current_company_currency is False

    def test_without_a_company_in_context_it_is_false(self, mxn):
        assert mxn.is_current_company_currency is False


class TestMultiCurrencyGroup:
    """≙ ``_toggle_group_multi_currency`` (``:83-92``) y sus dos mitades."""

    def test_a_second_active_currency_activates_the_group(self, mxn, usd):
        """La pertenencia se **deriva del conteo**: nadie la escribe a mano.

        Qué haría fallar al control: no llamar al toggle desde ``save()``.
        """
        multi_id = IrModelData.xmlid_to_res_id('base.group_multi_currency')
        user_id = IrModelData.xmlid_to_res_id('base.group_user')
        if not multi_id or not user_id:
            pytest.skip('la siembra no dejó los dos xmlid')
        group_user = ResGroups.objects.get(pk=user_id)
        assert group_user.implied_ids.filter(pk=multi_id).exists()

    def test_deactivating_down_to_one_removes_it(self, db):
        """El otro lado, y el que hace que el toggle no sea un ``activate``.

        Qué haría fallar al control: no llamar nunca a
        ``_deactivate_group_multi_currency``.
        """
        multi_id = IrModelData.xmlid_to_res_id('base.group_multi_currency')
        user_id = IrModelData.xmlid_to_res_id('base.group_user')
        if not multi_id or not user_id:
            pytest.skip('la siembra no dejó los dos xmlid')
        ResCurrency.objects.update(active=False)
        ResCurrency._toggle_group_multi_currency()
        group_user = ResGroups.objects.get(pk=user_id)
        assert not group_user.implied_ids.filter(pk=multi_id).exists()


class TestCompanyCurrencyStaysActive:
    """≙ ``_check_company_currency_stays_active`` (``odoo19c: :105-115``)."""

    def test_a_currency_used_by_a_company_cannot_be_archived(
            self, mxn, company):
        """Qué haría fallar al control: quitar la guarda.

        Sin ella la empresa apunta a una moneda inactiva y todo importe suyo
        se convierte contra una tasa que ya nadie mantiene.
        """
        mxn.active = False
        with pytest.raises(ValidationError):
            mxn.save()

    def test_an_unused_currency_can_be_archived(self, usd):
        """El control positivo: sin él, una guarda que rechazara todo archivo
        pasaría el caso anterior."""
        usd.active = False
        usd.save()
        usd.refresh_from_db()
        assert usd.active is False

    def test_force_deactivate_lifts_the_guard(self, mxn, company):
        """La exención que la fuente declara para los tests, portada con su
        nombre."""
        mxn.active = False
        with context_scope(force_deactivate=True):
            mxn.save()
        mxn.refresh_from_db()
        assert mxn.active is False


class TestGetAllCurrencies:
    """≙ ``get_all_currencies`` (``odoo19c: res_currency.py:262-269``)."""

    def test_it_publishes_the_five_keys_of_the_source(self, mxn):
        listing = ResCurrency.get_all_currencies()
        assert listing[mxn.pk] == {
            'name': mxn.name, 'symbol': mxn.symbol,
            'position': mxn.position, 'digits': [69, mxn.decimal_places],
        }

    def test_an_archived_currency_is_not_listed(self, usd):
        """Qué haría fallar al control: no filtrar por ``active``."""
        usd.active = False
        usd.save()
        assert usd.pk not in ResCurrency.get_all_currencies()

    def test_writing_a_currency_invalidates_the_cache(self, mxn):
        """Qué haría fallar al control: cachear sin invalidar.

        Sin la invalidación, el símbolo viejo se sirve indefinidamente — que
        es el defecto entero que los tres puntos de escritura de la fuente
        existen para evitar.
        """
        ResCurrency.get_all_currencies()          # puebla el caché
        mxn.write({'symbol': '@'})
        assert ResCurrency.get_all_currencies()[mxn.pk]['symbol'] == '@'

    def test_the_cache_is_actually_used(self, mxn):
        """El control positivo del anterior: sin él, no cachear nunca pasaría
        el caso de la invalidación."""
        ResCurrency.get_all_currencies()
        assert cache.get(ResCurrency._all_currencies_cache_key()) is not None


class TestFormat:
    """≙ ``format`` (``:212-221``), sobre ``tools.format_amount``."""

    def test_the_amount_carries_its_symbol(self, mxn):
        formatted = mxn.format(Decimal('1234.5'))
        assert mxn.symbol in formatted
        assert '1' in formatted and '234' in formatted

    def test_the_thousands_are_grouped(self, mxn):
        """Qué haría fallar al control: no agrupar.

        ``1234567.89`` sin agrupar no tiene separadores; agrupado tiene dos.
        """
        formatted = mxn.format(Decimal('1234567.89'))
        assert formatted.count(',') == 2

    def test_the_symbol_goes_where_the_currency_says(self, db):
        """Qué haría fallar al control: poner el símbolo siempre del mismo
        lado. Por eso el caso mide las dos posiciones."""
        after = ResCurrency.objects.create(name='XPA', symbol='@',
                                           rounding='0.01', position='after')
        before = ResCurrency.objects.create(name='XPB', symbol='#',
                                            rounding='0.01', position='before')
        assert after.format(Decimal('1')).endswith('@')
        assert before.format(Decimal('1')).startswith('#')

    def test_the_space_before_the_symbol_does_not_break(self, mxn):
        """El espacio duro no es cosmética: impide que un salto de línea
        separe la cifra de su símbolo.

        Qué haría fallar al control: usar un espacio normal.
        """
        assert ' ' in mxn.format(Decimal('1'))

    def test_it_rounds_to_the_currency_places(self, mxn):
        """Dos decimales para un ``rounding`` de ``0.01``."""
        formatted = mxn.format(Decimal('1.005'))
        assert formatted.split('.')[-1].rstrip(' $') == '01'


class TestAmountToText:
    """≙ ``amount_to_text`` (``odoo19c: res_currency.py:175-210``).

    **Este método tiene dos capas, y el caso mide las dos.**
    ``account_check_printing`` ya construyó su versión mexicana —
    ``«CIEN PESOS 50/100 M.N.»`` — y la cuelga con ``chain_method``. Es la
    misma estratificación de la referencia: ``base`` declara el genérico y
    una localización lo sobrescribe.

    ``chain_method`` en modo relevo invoca la previa **sólo si la nueva
    devuelve ``None``**; la mexicana siempre devuelve, así que gana. Por eso
    el genérico se mide **llamándolo directo**, no por el atributo.
    """

    def test_the_localized_layer_wins_through_the_chain(self, mxn):
        """Qué haría fallar al control: que el genérico desplazara al
        mexicano.

        Es el riesgo real de añadir un método base donde antes no había
        ninguno: ``chain_method`` pasa de instalación directa a encadenado, y
        el orden decide qué lee un talonario.
        """
        assert mxn.amount_to_text(Decimal('1.5')) == 'UN PESOS 50/100 M.N.'

    def test_the_generic_layer_degrades_without_the_library(self, mxn):
        """El genérico, medido por su función y no por el atributo.

        Qué haría fallar al control: dejar que el ``NameError`` suba cuando
        ``num2words`` falta. El día que la biblioteca esté, este caso cambia
        de rama sin tocar el código — por eso comprueba la condición, no el
        resultado.
        """
        installed = ResCurrency.__dict__.get('amount_to_text')
        generic = getattr(installed, '_chain_previous', None)
        assert generic is not None, (
            'el atributo instalado tiene que ser el ENVOLTORIO de la cadena, '
            'con el genérico de base como eslabón previo. Si es None, o la '
            'localización desplazó al genérico, o el genérico no existe.')
        if res_currency.num2words is None:
            assert generic(mxn, Decimal('1.5')) == ''
        else:
            text = generic(mxn, Decimal('1.5'))
            assert mxn.currency_unit_label in text
            assert mxn.currency_subunit_label in text


class TestViewLabels:
    """≙ ``_get_view`` (``:328-343``) y ``_get_view_cache_key`` (``:321-326``)."""

    def test_the_four_rate_fields_get_a_label(self, mxn, company):
        """La fuente empareja ``company_rate`` con ``rate`` bajo un rótulo, e
        ``inverse_company_rate`` con ``inverse_rate`` bajo el otro. Cuatro
        campos, no dos.

        Qué haría fallar al control: rotular sólo los dos de la tasa.
        """
        with company_scope(company.pk):
            labels = ResCurrency._get_view()
        assert set(labels) == {'company_rate', 'rate',
                               'inverse_company_rate', 'inverse_rate'}
        assert labels['rate'] == labels['company_rate']
        assert labels['inverse_rate'] == labels['inverse_company_rate']
        assert labels['rate'] != labels['inverse_rate']

    def test_it_applies_to_the_form_too(self, mxn, company):
        """A diferencia de ``res.currency.rate``, aquí la fuente toca ``list``
        **y** ``form``.

        Qué haría fallar al control: copiar la condición de la otra clase.
        """
        with company_scope(company.pk):
            assert ResCurrency._get_view(view_type='form')
            assert ResCurrency._get_view(view_type='list')
            assert ResCurrency._get_view(view_type='kanban') == {}

    def test_the_cache_key_varies_with_the_company_currency(
            self, mxn, usd, company):
        other = ResCompany.objects.create(code='cur-co2', name='Cur Co Two',
                                          currency=usd)
        with company_scope(company.pk):
            k1 = ResCurrency._get_view_cache_key()
        with company_scope(other.pk):
            k2 = ResCurrency._get_view_cache_key()
        assert k1 != k2


class TestSelectCompaniesRates:
    """≙ ``_select_companies_rates`` (``odoo19c: res_currency.py:304-319``)."""

    def test_the_sql_runs_and_gives_the_validity_window(
            self, mxn, usd, company):
        """Qué haría fallar al control: un SQL que no compile contra nuestro
        esquema.

        No basta con que el método devuelva una cadena: se **ejecuta**. Las
        dos tasas sembradas tienen que salir con ``date_end`` encadenado — la
        primera termina donde empieza la segunda, y la última no termina.
        """
        _rate(usd, date(2026, 1, 1), 20, company)
        _rate(usd, date(2026, 3, 1), 25, company)
        with connection.cursor() as cursor:
            cursor.execute(
                f'SELECT currency_id, rate, date_start, date_end FROM '
                f'({ResCurrency._select_companies_rates()}) AS w '
                f'WHERE currency_id = %s ORDER BY date_start', [usd.pk])
            rows = cursor.fetchall()
        assert [(r[2], r[3]) for r in rows] == [
            (date(2026, 1, 1), date(2026, 3, 1)),
            (date(2026, 3, 1), None),
        ]
