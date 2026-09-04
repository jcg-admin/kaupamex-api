"""Los cuatro productores de SQL de ``account.invoice.report``.

≙ ``odoo19c: addons/account/report/account_invoice_report.py:78-148``.

Lo que estos casos miden, y lo que **no**: miden que ``_select``/``_from``/
``_where``/``_table_query`` emitan el SQL de la fuente y que ``_from``
incruste de verdad la tabla de divisas que ``ResCurrency`` produce. **No**
miden que la vista se pueda crear: eso depende de 14 columnas que
``account_move`` y ``account_move_line`` todavía no declaran (medido; ver el
docstring del módulo portado y la tarea #989), y por eso no hay aquí ningún
caso que ejecute un ``CREATE VIEW``.
"""
import pytest

from addons.account.report.account_invoice_report import AccountInvoiceReport
from addons.base.models.res_company import ResCompany
from addons.base.models.res_currency import ResCurrency
from orm.environments import activate_companies, company_scope
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
    return ResCompany.objects.create(
        code='acme-inv', name='ACME', currency=mxn_currency)


@pytest.fixture
def foreign(db, usd_currency):
    return ResCompany.objects.create(
        code='foreign-inv', name='Foreign', currency=usd_currency)


class TestTheSelectClause:
    """≙ ``_select`` (``:81-127``)."""

    def test_it_is_a_sql_object_with_no_parameters(self):
        sql = AccountInvoiceReport._select()
        assert isinstance(sql, SQL)
        # La cláusula es texto puro: ningún valor viaja como parámetro, así que
        # componerla con las otras dos no desplaza índices de marcador.
        assert sql.params == []

    def test_it_converts_every_monetary_column_with_the_currency_rate(self):
        code = AccountInvoiceReport._select().code
        # Las cinco columnas que la fuente multiplica por la tasa. Sin ellas un
        # reporte multi-empresa sumaría pesos con dólares.
        assert code.count('account_currency_table.rate') == 5
        for columna in ('AS price_subtotal', 'AS price_average',
                        'AS price_margin', 'AS inventory_value'):
            assert columna in code

    def test_it_flips_the_sign_of_the_reversing_document_types(self):
        code = AccountInvoiceReport._select().code
        # La factura de proveedor y la nota de crédito de cliente invierten el
        # signo: se registran del lado contrario del asiento.
        assert "'in_invoice','out_refund','in_receipt'" in code

    def test_it_falls_back_to_the_commercial_partner_country(self):
        assert ('COALESCE(partner.country_id, commercial_partner.country_id)'
                in AccountInvoiceReport._select().code)


class TestTheFromClause:
    """≙ ``_from`` (``:128-141``)."""

    def test_it_joins_the_currency_table_of_the_active_companies(
            self, company, mxn_currency):
        with company_scope(company.pk):
            sql = AccountInvoiceReport._from()
        # Una sola empresa → camino mono: la tabla de divisas es un VALUES
        # incrustado, no una tabla temporal.
        assert 'account_currency_table.company_id = line.company_id' in sql.code
        assert 'VALUES' in sql.code

    def test_it_names_the_temporary_table_when_the_companies_differ(
            self, company, foreign, mxn_currency, usd_currency):
        with company_scope(company.pk):
            # company_scope activa una; el multi se fuerza pidiendo las dos.
            activate_companies([company.pk, foreign.pk],
                               [company.pk, foreign.pk])
            sql = AccountInvoiceReport._from()
        assert 'JOIN account_currency_table ON' in sql.code
        assert 'VALUES' not in sql.code

    def test_it_declares_the_nine_joins_of_the_source(self, company):
        with company_scope(company.pk):
            code = AccountInvoiceReport._from().code
        for tabla in ('res_partner partner', 'product_product product',
                      'account_account account', 'product_template template',
                      'uom_uom uom_line', 'uom_uom uom_template',
                      'account_move move', 'res_partner commercial_partner'):
            assert tabla in code, tabla


class TestTheWhereClause:
    """≙ ``_where`` (``:142-148``)."""

    def test_it_keeps_only_the_six_invoice_document_types(self):
        code = AccountInvoiceReport._where().code
        for tipo in ('out_invoice', 'out_refund', 'in_invoice', 'in_refund',
                     'out_receipt', 'in_receipt'):
            assert "'%s'" % tipo in code

    def test_it_drops_the_section_and_note_lines(self):
        # ``display_type = 'product'`` deja fuera las líneas de sección y de
        # nota, que no llevan importe y falsearían todo agregado.
        assert "line.display_type = 'product'" in AccountInvoiceReport._where().code


class TestTheWholeQuery:
    """≙ ``_table_query`` (``:78-80``)."""

    def test_it_composes_the_three_clauses_in_order(self, company):
        with company_scope(company.pk):
            code = AccountInvoiceReport()._table_query.code
        assert code.index('SELECT') < code.index('FROM account_move_line')
        assert code.index('FROM account_move_line') < code.index('WHERE move.move_type')

    def test_it_carries_the_parameters_of_the_currency_table(self, company):
        with company_scope(company.pk):
            sql = AccountInvoiceReport()._table_query
        # El camino mono lleva la tasa y el redondeo como parámetros reales: si
        # la composición los perdiera, el VALUES quedaría con marcadores sin
        # valor y la vista fallaría al crearse.
        assert sql.params, 'la tabla de divisas aporta parámetros'


class TestTheAggregateOverride:
    """≙ ``_read_group_select`` (``:149-156``) — bloqueado, y lo declara."""

    def test_it_names_read_group_as_its_blocker_not_field_to_sql(self, company):
        with pytest.raises(NotImplementedError) as excinfo:
            AccountInvoiceReport()._read_group_select('price_average:avg', None)
        mensaje = str(excinfo.value)
        assert 'read_group' in mensaje
        # La cita anterior culpaba a _field_to_sql, que sí existe: el mensaje
        # tiene que decirlo para que nadie vuelva a perseguir ese bloqueo.
        assert '_field_to_sql si existe' in mensaje
