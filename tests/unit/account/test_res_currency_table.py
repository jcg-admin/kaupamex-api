"""La tabla de divisas del reporte — ≙ ``odoo19c: account/res_currency.py:42-283``.

Los ocho métodos que ``account`` le cuelga a ``res.currency`` para que un
reporte multi-empresa convierta importes a la moneda de la empresa activa.

Lo que estos casos miden, y lo que **no**: miden la **forma del SQL** que cada
constructor emite y el despacho entre el camino mono y el multi. No miden el
resultado de la conversión — eso exige un reporte que la consuma, y ninguno
está portado todavía (tarea #136, el motor de fórmulas de ``account.report``).
"""
import datetime

import pytest

from addons.base.models.res_company import ResCompany
from addons.base.models.res_currency import ResCurrency
from orm.environments import company_scope, execute_query
from tools.sql import SQL


@pytest.fixture
def mxn_currency(db):
    return ResCurrency.objects.get_or_create(
        name='MXN', defaults={'symbol': '$'})[0]


@pytest.fixture
def usd_currency(db):
    return ResCurrency.objects.get_or_create(
        name='USD', defaults={'symbol': 'US$'})[0]


@pytest.fixture
def company(db, mxn_currency):
    return ResCompany.objects.create(code='acme', name='ACME', currency=mxn_currency)


@pytest.fixture
def foreign(db, usd_currency):
    return ResCompany.objects.create(code='foreign', name='Foreign', currency=usd_currency)


@pytest.mark.django_db
class TestTheMonoVersusMultiDispatch:
    """``_check_currency_table_monocurrency`` — ≙ ``:52-58``."""

    def test_a_single_currency_is_monocurrency(self, company):
        assert ResCurrency._check_currency_table_monocurrency([company]) is True

    def test_two_different_currencies_are_not(self, company, foreign):
        assert ResCurrency._check_currency_table_monocurrency(
            [company, foreign]) is False

    def test_two_companies_sharing_a_currency_are(self, company, mxn_currency):
        hermana = ResCompany.objects.create(
            code='hermana', name='Hermana', currency=mxn_currency)
        assert ResCurrency._check_currency_table_monocurrency(
            [company, hermana]) is True

    def test_it_does_not_load_each_company_currency(self, company, mxn_currency,
                                                 django_assert_num_queries):
        """Lee la PK del descriptor de la FK, no el objeto — 0 consultas.

        Este caso reemplaza a uno anterior que afirmaba que un conjunto de
        instancias «no deduplicaría». **Medido: sí deduplica** —
        ``Model.__hash__`` es ``hash(self.pk)``—, así que aquel caso pasaba con
        las dos implementaciones y no medía nada (el sub-patrón D de
        ``metrica-decide-la-conclusion``). Lo que sí las distingue es la
        consulta: con ``c.currency`` habría una por empresa.
        """
        ResCompany.objects.create(code='hermana', name='Hermana', currency=mxn_currency)
        # Recién traídas de la base: sin esto la FK ya está en la caché de la
        # instancia y ``c.currency`` tampoco consultaría — el caso pasaría con
        # las dos implementaciones y volvería a no medir nada.
        frescas = list(ResCompany.objects.filter(
            code__in=['acme', 'hermana']))
        with django_assert_num_queries(0):
            assert ResCurrency._check_currency_table_monocurrency(
                frescas) is True


@pytest.mark.django_db
class TestTheMonocurrencyTable:
    """``_get_monocurrency_currency_table_sql`` — ≙ ``:60-72``."""

    def test_it_emits_values_with_the_source_alias(self, company):
        sql = ResCurrency._get_monocurrency_currency_table_sql([company])
        assert sql.code.startswith('(VALUES ')
        assert 'AS account_currency_table(company_id, period_key, ' \
               'date_from, date_next, rate_type, rate)' in sql.code

    def test_without_cta_one_row_per_company(self, company, foreign):
        sql = ResCurrency._get_monocurrency_currency_table_sql(
            [company, foreign])
        assert sql.params.count('current') == 2
        assert 'historical' not in sql.params

    def test_with_cta_three_rows_per_company(self, company):
        sql = ResCurrency._get_monocurrency_currency_table_sql(
            [company], use_cta_rates=True)
        for tipo in ('historical', 'current', 'average'):
            assert tipo in sql.params
        assert sql.params.count(company.pk) == 3

    def test_the_sql_runs_against_postgresql(self, company):
        """Que la forma sea válida no se afirma: se ejecuta.

        Un ``VALUES`` mal formado se compila igual como cadena; sólo el motor
        lo rechaza.
        """
        tabla = ResCurrency._get_monocurrency_currency_table_sql([company])
        filas = execute_query(
            SQL('SELECT company_id, rate_type, rate FROM %s', tabla))
        assert filas == [(company.pk, 'current', 1)]


@pytest.mark.django_db
class TestTheTableBuilders:
    """Los cuatro ``_get_table_builder_*`` — ≙ ``:142-283``."""

    def test_domestic_emits_one_unit_rate_per_company(self, company):
        sql = ResCurrency._get_table_builder_domestic_currency(
            [company], use_cta_rates=False)
        assert "'current', 1" in sql.code
        assert "'average', 1" not in sql.code

    def test_domestic_with_cta_emits_the_three_types(self, company):
        sql = ResCurrency._get_table_builder_domestic_currency(
            [company], use_cta_rates=True)
        for tipo in ("'current', 1", "'average', 1", "'historical', 1"):
            assert tipo in sql.code

    def test_current_uses_any_not_in(self, company, foreign):
        """El control de :ref:`h-api-907`.

        ``IN %(...)s`` con una tupla lo adapta psycopg3 como literal de
        registro y da ``syntax error``; ``= ANY(array)`` con una lista es la
        forma que sí acepta. Si alguien revirtiera la adaptación, este caso
        cae — y el siguiente, que ejecuta, también.
        """
        sql = ResCurrency._get_table_builder_current(
            'periodo', company, [foreign], datetime.date(2026, 8, 29), 1)
        assert 'other_company.id = ANY(' in sql.code
        assert 'other_company.id IN ' not in sql.code
        assert [foreign.pk] in sql.params

    def test_current_runs_against_postgresql(self, company, foreign):
        sql = ResCurrency._get_table_builder_current(
            'periodo', company, [foreign], datetime.date(2026, 8, 29), 1)
        filas = execute_query(sql)
        # Sin ``res.currency.rate`` sembrada, el LEFT JOIN no encuentra tasa y
        # el CASE cae a 1 — ≙ ``:172`` de la fuente.
        assert filas == [(foreign.pk, 'periodo', None, None, 'current', 1)]

    def test_historical_runs_and_excludes_by_date(self, company, foreign):
        sql = ResCurrency._get_table_builder_historical(
            company, [foreign], datetime.date(2026, 8, 29), 1,
            datetime.date(2026, 1, 1))
        assert 'AND rate.name > ' in sql.code
        assert execute_query(sql) == []   # sin tasas sembradas

    def test_historical_without_exclusion_omits_the_condition(self, company,
                                                            foreign):
        sql = ResCurrency._get_table_builder_historical(
            company, [foreign], datetime.date(2026, 8, 29), 1, None)
        assert 'AND rate.name > ' not in sql.code

    def test_average_without_date_from_takes_the_year_start(self, company,
                                                          foreign):
        """≙ ``:220-222``: sin fecha inicial, promedia el año en curso.

        Es el consumidor de ``fields.Date.from_string`` y de
        ``date_utils.start_of`` que motivó el porte de ``fields_temporal``.
        """
        sql = ResCurrency._get_table_builder_average(
            'periodo', company, [foreign], None, '2026-08-29', 1)
        assert datetime.date(2026, 1, 1) in sql.params

    def test_average_runs_against_postgresql(self, company, foreign):
        sql = ResCurrency._get_table_builder_average(
            'periodo', company, [foreign], datetime.date(2026, 1, 1),
            datetime.date(2026, 8, 29), 1)
        # Sin tasas dentro del periodo, la rama UNION ALL aporta la fila de
        # respaldo con tasa 1.0 — ≙ ``:255``.
        filas = execute_query(sql)
        assert [f[0] for f in filas] == [foreign.pk]


@pytest.mark.django_db
class TestTheTemporaryTable:
    """``_create_currency_table`` y ``_get_simple_currency_table`` — ≙ ``:42-140``."""

    def test_mono_returns_the_values_without_creating_a_table(self, company):
        with company_scope(company.pk):
            sql = ResCurrency._get_simple_currency_table([company])
        assert sql.code.startswith('(VALUES ')

    def test_multi_creates_the_temporary_table_and_names_it(self, company, foreign):
        with company_scope(company.pk):
            sql = ResCurrency._get_simple_currency_table([company, foreign])
        assert sql.code == 'account_currency_table'

        filas = execute_query(SQL(
            'SELECT company_id, rate_type, rate FROM account_currency_table '
            'ORDER BY company_id'))
        # La empresa doméstica entra con tasa 1 por el builder domestic; la
        # extranjera, por el builder current.
        assert sorted(f[0] for f in filas) == sorted([company.pk, foreign.pk])
        assert {f[1] for f in filas} == {'current'}

    def test_the_table_is_regenerated_within_the_same_transaction(self, company,
                                                          foreign):
        """≙ el ``DROP TABLE IF EXISTS`` de ``:120``.

        La fuente lo declara porque sus pruebas llaman dos veces dentro de la
        misma transacción. Aquí se ejercita igual: sin el DROP, la segunda
        llamada fallaría con ``relation already exists``.
        """
        with company_scope(company.pk):
            ResCurrency._get_simple_currency_table([company, foreign])
            ResCurrency._get_simple_currency_table([company, foreign])
        assert execute_query(
            SQL('SELECT count(*) FROM account_currency_table')) == [(2,)]
