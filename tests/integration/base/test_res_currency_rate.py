"""Tests — ``res.currency.rate``: cabecera, restricciones y las tres tasas.

Contrato adaptado de ``odoo19c: odoo/addons/base/models/res_currency.py``,
clase ``ResCurrencyRate`` (``:346-400`` la declaración, ``:388-478`` los
métodos).

**Qué haría fallar a cada control se declara en su caso.** Un control cuyo
verde no distingue *"el porte funciona"* de *"el caso no pregunta"* no es una
red — es un adorno (sub-patrón D de ``metrica-decide-la-conclusion.md``).
"""
from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from addons.base.models import ResCompany, ResCurrency
from addons.base.models.res_currency_rate import ResCurrencyRate
from orm.environments import company_scope

pytestmark = pytest.mark.integration


@pytest.fixture
def currency(db):
    return ResCurrency.objects.create(name='XTS', symbol='X', rounding='0.01')


@pytest.fixture
def other_currency(db):
    return ResCurrency.objects.create(name='XTT', symbol='Y', rounding='0.01')


@pytest.fixture
def company(db, currency):
    return ResCompany.objects.create(code='rate-co', name='Rate Co',
                                     currency=currency)


class TestClassAttributes:
    """≙ los cuatro de ``odoo19c: res_currency.py:347-350``."""

    def test_the_four_attributes_of_the_source_are_declared(self):
        """Qué haría fallar al control: borrar cualquiera de los cuatro.

        La regla ``atributos-de-clase-de-modelo.md`` es condicional: si la
        clase de la fuente declara atributos, se portan TODOS. Ésta declara
        cinco; el quinto (``_check_company_domain``) no tiene receptor y su
        conducta la cubre ``_check_company_id``, que sí se porta.
        """
        assert ResCurrencyRate._name == 'res.currency.rate'
        assert ResCurrencyRate._description == 'Currency Rate'
        assert ResCurrencyRate._rec_names_search == ['name', 'rate']
        assert ResCurrencyRate._order == 'name desc, id'

    def test_the_table_matches_the_dotted_name(self):
        assert (ResCurrencyRate._meta.db_table
                == ResCurrencyRate._name.replace('.', '_'))

    def test_the_ordering_derives_from_the_declared_order(self):
        """``name desc, id`` → ``['-name', 'id']``.

        Qué haría fallar al control: dejar ``ordering = ['name']``. El
        siguiente caso lo mide contra la base, no sólo contra la declaración.
        """
        assert ResCurrencyRate._meta.ordering == ['-name', 'id']

    def test_the_newest_rate_leads_the_listing(self, currency):
        """Qué haría fallar al control: invertir el signo del orden.

        La tasa **más reciente** encabeza: es la que vale hoy. Con el orden
        ascendente encabezaría la más vieja, que es la respuesta equivocada
        para todo consumidor de conversión.
        """
        for day in (1, 15, 28):
            ResCurrencyRate.objects.create(
                currency=currency, name=date(2026, 3, day), rate=Decimal('2'))
        listed = list(ResCurrencyRate.objects.filter(
            currency=currency).values_list('name', flat=True))
        assert listed == [date(2026, 3, 28), date(2026, 3, 15),
                          date(2026, 3, 1)]


class TestUniquePerDay:
    """≙ ``_unique_name_per_day`` (``odoo19c: res_currency.py:379-382``)."""

    def test_two_rates_for_the_same_day_and_currency_are_rejected(
            self, currency, company):
        """Qué haría fallar al control: retirar la ``UniqueConstraint``.

        Dos tasas del mismo día para la misma moneda y empresa hacen que
        ``_get_latest_rate`` devuelva una de las dos según el orden de
        inserción — la conversión deja de ser determinista.
        """
        ResCurrencyRate.objects.create(currency=currency, company=company,
                                       name=date(2026, 3, 1),
                                       rate=Decimal('2'))
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ResCurrencyRate.objects.create(
                    currency=currency, company=company,
                    name=date(2026, 3, 1), rate=Decimal('3'))

    def test_the_same_day_for_another_currency_is_allowed(
            self, currency, other_currency, company):
        """El control positivo: la restricción es por trío, no por fecha.

        Qué haría fallar al control: poner ``fields=['name']`` a secas. Sin
        este caso, una restricción demasiado ancha pasaría el caso anterior
        y rompería toda instalación multi-divisa en silencio.
        """
        ResCurrencyRate.objects.create(currency=currency, company=company,
                                       name=date(2026, 3, 1),
                                       rate=Decimal('2'))
        second = ResCurrencyRate.objects.create(
            currency=other_currency, company=company,
            name=date(2026, 3, 1), rate=Decimal('3'))
        assert second.pk is not None


class TestRateCheckConstraint:
    """≙ ``_currency_rate_check`` (``odoo19c: res_currency.py:383-386``)."""

    @pytest.mark.parametrize('bad', [Decimal('0'), Decimal('-1.5')])
    def test_a_non_positive_rate_is_rejected(self, currency, bad):
        """Qué haría fallar al control: retirar la ``CheckConstraint``.

        No es defensa cosmética: con ``rate = 0`` toda conversión que la use
        da 0, y ``_compute_inverse_company_rate`` divide entre ella.

        Una mutación del ``Meta.constraints`` **no** haría caer este caso
        bajo ``--reuse-db`` — la restricción vive en la base migrada, no en
        la declaración. El control que sí discrimina la retira de la base:
        ``test_res_currency_rate_constraint_control.py``.
        """
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ResCurrencyRate.objects.create(
                    currency=currency, name=date(2026, 3, 1), rate=bad)

    def test_a_positive_rate_is_accepted(self, currency):
        """El control positivo de la restricción."""
        row = ResCurrencyRate.objects.create(
            currency=currency, name=date(2026, 3, 1), rate=Decimal('0.0001'))
        assert row.pk is not None


class TestGetLatestRate:
    """≙ ``_get_latest_rate`` (``odoo19c: res_currency.py:404-412``)."""

    def test_the_date_of_the_same_day_is_not_its_own_predecessor(
            self, currency, company):
        """Qué haría fallar al control: cambiar ``name__lt`` por ``name__lte``.

        La fuente compara con ``<`` estricto. Con ``<=`` una tasa se
        encontraría a sí misma como anterior, y ``_compute_company_rate``
        devolvería siempre 1.
        """
        today = ResCurrencyRate.objects.create(
            currency=currency, company=company, name=date(2026, 3, 15),
            rate=Decimal('5'))
        assert today._get_latest_rate() is None

    def test_it_returns_the_closest_earlier_rate(self, currency, company):
        """Qué haría fallar al control: ordenar ascendente y tomar el primero.

        Con dos tasas anteriores gana la **más cercana**, no la más vieja.
        Un solo predecesor no distinguiría las dos implementaciones — por eso
        el caso siembra dos.
        """
        ResCurrencyRate.objects.create(currency=currency, company=company,
                                       name=date(2026, 1, 1),
                                       rate=Decimal('2'))
        ResCurrencyRate.objects.create(currency=currency, company=company,
                                       name=date(2026, 2, 1),
                                       rate=Decimal('3'))
        current = ResCurrencyRate.objects.create(
            currency=currency, company=company, name=date(2026, 3, 1),
            rate=Decimal('4'))
        assert current._get_latest_rate().rate == Decimal('3')

    def test_a_rate_of_another_currency_is_not_a_predecessor(
            self, currency, other_currency, company):
        """Qué haría fallar al control: quitar el filtro por moneda.

        Sin él, la tasa del euro sería el predecesor de la del peso.
        """
        ResCurrencyRate.objects.create(currency=other_currency,
                                       company=company,
                                       name=date(2026, 1, 1),
                                       rate=Decimal('9'))
        current = ResCurrencyRate.objects.create(
            currency=currency, company=company, name=date(2026, 3, 1),
            rate=Decimal('4'))
        assert current._get_latest_rate() is None

    def test_a_rate_without_a_date_raises(self, currency):
        """≙ el ``UserError`` de ``:406-407``.

        Qué haría fallar al control: borrar la guarda. Sin ella el filtro
        ``name__lt=None`` devuelve el conjunto vacío en silencio, y el
        llamador lee «no hay tasa anterior» donde la verdad es «falta la
        fecha».
        """
        orphan = ResCurrencyRate(currency=currency, rate=Decimal('4'))
        with pytest.raises(ValidationError):
            orphan._get_latest_rate()


class TestLastRatesForCompanies:
    """≙ ``_get_last_rates_for_companies`` (``odoo19c: :414-421``)."""

    def test_without_any_rate_the_company_measures_one(self, company):
        """Qué haría fallar al control: quitar la caída a 1.

        Sin ella el divisor es ``None`` y ``_compute_company_rate`` revienta
        en toda instalación recién creada.
        """
        rates = ResCurrencyRate._get_last_rates_for_companies([company])
        assert rates[company.pk] == Decimal('1.0')

    def test_a_global_rate_counts_for_the_company(self, currency, company):
        """Qué haría fallar al control: filtrar sólo ``company=company``.

        La fuente admite la tasa **sin empresa** — es la global. Sin esa
        rama, una instalación que sólo declara tasas globales mediría 1
        siempre y toda conversión saldría sin convertir.
        """
        ResCurrencyRate.objects.create(currency=currency, company=None,
                                       name=date(2026, 3, 1),
                                       rate=Decimal('7'))
        rates = ResCurrencyRate._get_last_rates_for_companies([company])
        assert rates[company.pk] == Decimal('7')

    def test_the_latest_wins_over_the_older(self, currency, company):
        """Qué haría fallar al control: tomar el primero en vez del último."""
        ResCurrencyRate.objects.create(currency=currency, company=company,
                                       name=date(2026, 1, 1),
                                       rate=Decimal('2'))
        ResCurrencyRate.objects.create(currency=currency, company=company,
                                       name=date(2026, 3, 1),
                                       rate=Decimal('8'))
        rates = ResCurrencyRate._get_last_rates_for_companies([company])
        assert rates[company.pk] == Decimal('8')


class TestTheThreeRates:
    """≙ ``_compute_rate`` / ``_compute_company_rate`` y sus inversos."""

    def test_compute_rate_falls_back_to_the_previous_one(
            self, currency, company):
        """≙ ``:423-425``.

        Qué haría fallar al control: devolver 1 en vez de consultar la
        anterior. Se siembra una tasa previa de 3 para que las dos
        implementaciones den resultados distintos.
        """
        ResCurrencyRate.objects.create(currency=currency, company=company,
                                       name=date(2026, 1, 1),
                                       rate=Decimal('3'))
        fresh = ResCurrencyRate(currency=currency, company=company,
                                name=date(2026, 3, 1), rate=None)
        assert fresh._compute_rate() == Decimal('3')

    def test_compute_rate_falls_back_to_one_without_any_predecessor(
            self, currency, company):
        fresh = ResCurrencyRate(currency=currency, company=company,
                                name=date(2026, 3, 1), rate=None)
        assert fresh._compute_rate() == Decimal('1.0')

    def test_company_rate_divides_by_the_company_currency_rate(
            self, currency, other_currency, company):
        """≙ ``:427-431``.

        La moneda de la empresa es ``currency``, cuya última tasa vale 2. La
        fila es de ``other_currency`` y vale 8, así que ``8 / 2 = 4``.

        Qué haría fallar al control: devolver ``rate`` a secas. El divisor es
        2 y no 1 justamente para que las dos implementaciones difieran.

        **La fila es de OTRA moneda a propósito.** Con la fila en la moneda de
        la empresa, ella misma es su divisor y el cociente es 1 —correcto, y
        ciego: un ``return self.rate`` lo pasaría igual. Medido: la primera
        versión de este caso lo hacía así y daba 1.
        """
        ResCurrencyRate.objects.create(currency=currency, company=company,
                                       name=date(2026, 1, 1),
                                       rate=Decimal('2'))
        row = ResCurrencyRate.objects.create(
            currency=other_currency, company=company, name=date(2026, 3, 1),
            rate=Decimal('8'))
        assert row._compute_company_rate() == Decimal('4')

    def test_a_rate_in_the_company_currency_measures_one(
            self, currency, company):
        """El otro lado del caso anterior, y el que fija su premisa.

        Una tasa de la moneda de la propia empresa es su propio divisor: el
        cociente es 1. Qué haría fallar al control: hacer que el divisor
        excluya la fila que se está calculando.
        """
        row = ResCurrencyRate.objects.create(
            currency=currency, company=company, name=date(2026, 3, 1),
            rate=Decimal('8'))
        assert row._compute_company_rate() == Decimal('1')

    def test_inverse_company_rate_writes_back_the_stored_rate(
            self, currency, company):
        """≙ ``:433-437`` — el lado de escritura.

        Es el par del caso anterior: escribir ``company_rate = 4`` con un
        divisor de 2 tiene que reconstruir ``rate = 8``. Qué haría fallar al
        control: multiplicar por 1 (ignorar el divisor).
        """
        ResCurrencyRate.objects.create(currency=currency, company=company,
                                       name=date(2026, 1, 1),
                                       rate=Decimal('2'))
        row = ResCurrencyRate(currency=currency, company=company,
                              name=date(2026, 3, 1), rate=Decimal('8'))
        assert row._inverse_company_rate(Decimal('4')) == Decimal('8')

    def test_the_two_derived_rates_are_reciprocal(
            self, currency, other_currency, company):
        """≙ ``:439-443``.

        Qué haría fallar al control: devolver ``company_rate`` sin invertir.
        Con el divisor en 2 y la fila en 8, ``company_rate`` es 4 y su
        recíproco 0.25 — dos valores distintos, así que el caso discrimina.

        La fila va en ``other_currency`` por el mismo motivo que el caso de
        arriba: en la moneda de la empresa el cociente sería 1 y su recíproco
        también, y los dos lados dejarían de distinguirse.
        """
        ResCurrencyRate.objects.create(currency=currency, company=company,
                                       name=date(2026, 1, 1),
                                       rate=Decimal('2'))
        row = ResCurrencyRate.objects.create(
            currency=other_currency, company=company, name=date(2026, 3, 1),
            rate=Decimal('8'))
        assert row._compute_company_rate() == Decimal('4')
        assert row._compute_inverse_company_rate() == Decimal('0.25')

    def test_writing_the_inverse_round_trips_to_the_stored_rate(
            self, currency, company):
        """≙ ``:445-449`` — el lado de escritura del recíproco."""
        ResCurrencyRate.objects.create(currency=currency, company=company,
                                       name=date(2026, 1, 1),
                                       rate=Decimal('2'))
        row = ResCurrencyRate(currency=currency, company=company,
                              name=date(2026, 3, 1), rate=Decimal('8'))
        assert row._inverse_inverse_company_rate(Decimal('0.25')) == Decimal('8')

    def test_a_falsy_inverse_falls_back_to_one(self, currency, company):
        """≙ la caída a 1 de ``:447-448``.

        Qué haría fallar al control: quitar el ``or 1``. Con 0 la línea
        siguiente divide entre cero.
        """
        row = ResCurrencyRate(currency=currency, company=company,
                              name=date(2026, 3, 1), rate=Decimal('8'))
        assert row._inverse_inverse_company_rate(Decimal('0')) == Decimal('1.0')


class TestCurrentCompanyResolution:
    """El ``self.env.company.root_id`` de la fuente, en cuatro sitios."""

    def test_the_company_in_context_resolves_to_its_root(
            self, currency, company):
        """Qué haría fallar al control: devolver la sucursal sin ``root_id``.

        ``_check_company_id`` prohíbe que una tasa cuelgue de una sucursal,
        así que buscar la anterior con la sucursal en contexto no encontraría
        ninguna. La tasa se siembra en la MATRIZ y se consulta desde la
        SUCURSAL: sin ``root_id`` el resultado es ``None``.
        """
        branch = ResCompany.objects.create(code='rate-br', name='Rate Branch',
                                           currency=currency, parent=company)
        ResCurrencyRate.objects.create(currency=currency, company=company,
                                       name=date(2026, 1, 1),
                                       rate=Decimal('3'))
        row = ResCurrencyRate(currency=currency, company=None,
                              name=date(2026, 3, 1), rate=Decimal('9'))
        with company_scope(branch.pk):
            latest = row._get_latest_rate()
        assert latest is not None and latest.rate == Decimal('3')


class TestOnchangeRateWarning:
    """≙ ``_onchange_rate_warning`` (``odoo19c: res_currency.py:451-464``)."""

    def test_a_move_beyond_twenty_percent_warns(self, currency, company):
        """Qué haría fallar al control: subir el umbral o quitar el aviso.

        De 100 a 50 es una caída del 50 %: bien por encima del 20 % de la
        fuente.
        """
        ResCurrencyRate.objects.create(currency=currency, company=company,
                                       name=date(2026, 1, 1),
                                       rate=Decimal('100'))
        row = ResCurrencyRate(currency=currency, company=company,
                              name=date(2026, 3, 1), rate=Decimal('50'))
        warning = row._onchange_rate_warning()
        assert warning is not None
        assert 'warning' in warning
        assert currency.name in warning['warning']['title']

    def test_a_move_within_twenty_percent_stays_quiet(self, currency, company):
        """El control negativo: sin él, un aviso incondicional también pasaría
        el caso anterior y el umbral no mediría nada.

        De 100 a 90 es un 10 %.
        """
        ResCurrencyRate.objects.create(currency=currency, company=company,
                                       name=date(2026, 1, 1),
                                       rate=Decimal('100'))
        row = ResCurrencyRate(currency=currency, company=company,
                              name=date(2026, 3, 1), rate=Decimal('90'))
        assert row._onchange_rate_warning() is None

    def test_the_exact_boundary_of_twenty_percent_stays_quiet(
            self, currency, company):
        """La fuente compara ``abs(diff) > 0.2``, no ``>=``.

        Qué haría fallar al control: usar ``>=``. De 100 a 80 el cociente es
        exactamente 0.2.
        """
        ResCurrencyRate.objects.create(currency=currency, company=company,
                                       name=date(2026, 1, 1),
                                       rate=Decimal('100'))
        row = ResCurrencyRate(currency=currency, company=company,
                              name=date(2026, 3, 1), rate=Decimal('80'))
        assert row._onchange_rate_warning() is None

    def test_without_a_predecessor_there_is_nothing_to_warn_about(
            self, currency, company):
        row = ResCurrencyRate(currency=currency, company=company,
                              name=date(2026, 3, 1), rate=Decimal('50'))
        assert row._onchange_rate_warning() is None


class TestCheckCompanyId:
    """≙ ``_check_company_id`` (``odoo19c: res_currency.py:473-477``)."""

    def test_a_rate_for_a_branch_company_is_rejected(self, currency, company):
        """Qué haría fallar al control: quitar la guarda de ``save()``.

        Una sucursal hereda la moneda de su raíz, así que una tasa colgada de
        ella describiría una moneda que no es suya.
        """
        branch = ResCompany.objects.create(code='rate-b2', name='Branch Two',
                                           currency=currency, parent=company)
        with pytest.raises(ValidationError):
            ResCurrencyRate.objects.create(
                currency=currency, company=branch, name=date(2026, 3, 1),
                rate=Decimal('2'))

    def test_a_rate_for_a_root_company_is_accepted(self, currency, company):
        """El control positivo: sin él, una guarda que rechazara TODO también
        pasaría el caso anterior."""
        row = ResCurrencyRate.objects.create(
            currency=currency, company=company, name=date(2026, 3, 1),
            rate=Decimal('2'))
        assert row.pk is not None

    def test_a_rate_without_company_is_accepted(self, currency):
        """La tasa global no tiene empresa que validar."""
        row = ResCurrencyRate.objects.create(
            currency=currency, company=None, name=date(2026, 3, 1),
            rate=Decimal('2'))
        assert row.pk is not None


class TestSanitizeVals:
    """≙ ``_sanitize_vals`` (``odoo19c: res_currency.py:388-393``)."""

    def test_rate_wins_over_company_rate(self):
        """Qué haría fallar al control: invertir la precedencia.

        El orden de la fuente es explícito: ``rate`` gana sobre
        ``company_rate``, y ``company_rate`` sobre ``inverse_company_rate``.
        """
        out = ResCurrencyRate._sanitize_vals(
            {'rate': 2, 'company_rate': 3})
        assert out == {'rate': 2}

    def test_company_rate_wins_over_the_inverse(self):
        out = ResCurrencyRate._sanitize_vals(
            {'company_rate': 3, 'inverse_company_rate': 4})
        assert out == {'company_rate': 3}

    def test_rate_wins_over_both(self):
        out = ResCurrencyRate._sanitize_vals(
            {'rate': 2, 'company_rate': 3, 'inverse_company_rate': 4})
        assert out == {'rate': 2}

    def test_a_lone_value_survives(self):
        """El control negativo: sin él, un ``_sanitize_vals`` que borrara
        siempre las dos derivadas pasaría los tres casos anteriores."""
        assert ResCurrencyRate._sanitize_vals(
            {'inverse_company_rate': 4}) == {'inverse_company_rate': 4}
        assert ResCurrencyRate._sanitize_vals(
            {'company_rate': 3}) == {'company_rate': 3}

    def test_the_caller_dict_is_not_mutated(self):
        """Qué haría fallar al control: borrar el ``dict(vals)`` de la primera
        línea. La fuente muta su argumento; aquí no, y esa diferencia tiene
        que ser observable o nadie la mantiene."""
        original = {'rate': 2, 'company_rate': 3}
        ResCurrencyRate._sanitize_vals(original)
        assert original == {'rate': 2, 'company_rate': 3}
