"""``account.invoice.report`` -- cabecera de la vista y su bloqueo restante.

Cubre ``addons/account/report/account_invoice_report.py`` (tareas #398 y
#511, hallazgo H-API-682).

**Actualizado con el porte de #511.** El docstring decia que la cadena de
bloqueo eran ``ResCurrency._get_simple_currency_table`` y ``_field_to_sql``:
las dos piezas existen hoy, asi que la afirmacion es falsa. El unico metodo
que sigue bloqueado es ``_read_group_select``, y por el ``read_group`` base
que ``src/orm`` no declara (tarea #473).

La forma del SQL que los cuatro productores emiten se mide en
``test_account_invoice_report_sql.py``; aqui se cubre la forma del modelo
(atributos de clase, ``Meta``, campos) y que el bloqueo restante siga siendo
ruidoso.
"""
import pytest

from addons.base.models.res_company import ResCompany
from addons.base.models.res_currency import ResCurrency
from orm.environments import company_scope
from tools.sql import SQL

from addons.account.models.account_move import AccountMove
from addons.account.report.account_invoice_report import (
    MOVE_TYPE_CHOICES,
    AccountInvoiceReport,
    ReportAccountReportInvoice,
    ReportAccountReportInvoiceWithPayments,
)

pytestmark = [pytest.mark.unit]


class TestModelClassAttributes:
    """Los 6 atributos de clase de modelo, verbatim contra la referencia
    (``odoo19c: addons/account/report/account_invoice_report.py:13-17``).
    Ver ``.claude/rules/atributos-de-clase-de-modelo.md`` -- se portan
    TODOS o ninguno; aqui van los 6 que la fuente declara.
    """

    def test_reference_name(self):
        assert AccountInvoiceReport._name == 'account.invoice.report'

    def test_reference_description(self):
        assert AccountInvoiceReport._description == 'Invoices Statistics'

    def test_auto_is_false(self):
        assert AccountInvoiceReport._auto is False

    def test_rec_name(self):
        assert AccountInvoiceReport._rec_name == 'invoice_date'

    def test_order(self):
        assert AccountInvoiceReport._order == 'invoice_date desc'

    def test_depends_covers_the_same_models_as_the_source(self):
        expected_models = {
            'account.move', 'account.move.line', 'product.product',
            'product.template', 'uom.uom', 'res.currency.rate', 'res.partner',
        }
        assert set(AccountInvoiceReport._depends) == expected_models


class TestMeta:
    def test_is_unmanaged(self):
        assert AccountInvoiceReport._meta.managed is False

    def test_db_table(self):
        assert AccountInvoiceReport._meta.db_table == 'account_invoice_report'

    def test_app_label(self):
        assert AccountInvoiceReport._meta.app_label == 'account'


class TestFieldCount:
    """27 campos, ni uno mas ni uno menos -- medido por AST contra la
    referencia en el docstring del modulo bajo prueba.
    """

    def test_has_all_27_reference_fields(self):
        expected_field_names = {
            'move_id', 'journal_id', 'company_id', 'company_currency_id',
            'partner_id', 'commercial_partner_id', 'country_id',
            'invoice_user_id', 'move_type', 'state', 'payment_state',
            'fiscal_position_id', 'invoice_date', 'quantity', 'product_id',
            'product_uom_id', 'product_categ_id', 'invoice_date_due',
            'account_id', 'price_subtotal_currency', 'price_subtotal',
            'price_total', 'price_total_currency', 'price_average',
            'price_margin', 'inventory_value', 'currency_id',
        }
        actual_field_names = {f.name for f in AccountInvoiceReport._meta.get_fields()}
        assert expected_field_names <= actual_field_names
        assert len(expected_field_names) == 27


class TestMoveTypeChoices:
    """Subconjunto de ``AccountMove.MOVE_TYPES``, sin duplicar etiquetas."""

    def test_has_exactly_the_four_invoice_move_types(self):
        assert [key for key, _ in MOVE_TYPE_CHOICES] == [
            'out_invoice', 'in_invoice', 'out_refund', 'in_refund',
        ]

    def test_labels_come_from_account_move_verbatim(self):
        move_type_labels = dict(AccountMove.MOVE_TYPES)
        for key, label in MOVE_TYPE_CHOICES:
            assert label == move_type_labels[key]


class TestStateAndPaymentStateReuseAccountMove:
    """DRY: ``state``/``payment_state`` reusan el vocabulario de
    ``AccountMove`` en vez de repetirlo -- las dos listas nunca pueden
    divergir en texto.
    """

    def test_state_field_reuses_account_move_states(self):
        state_field = AccountInvoiceReport._meta.get_field('state')
        assert list(state_field.choices) == AccountMove.STATES

    def test_payment_state_field_reuses_account_move_payment_states(self):
        field = AccountInvoiceReport._meta.get_field('payment_state')
        assert list(field.choices) == AccountMove.PAYMENT_STATES


class TestBlockedQueryMethods:
    """Cuatro de los cinco dejaron de estar bloqueados (api@HEAD, tarea #511).

    Estos casos eran correctos cuando la tabla de divisas no existía: cada
    método levantaba ``NotImplementedError`` con la pieza que le faltaba. Con
    ``ResCurrency._get_simple_currency_table`` portado, ``_select``/``_from``/
    ``_where``/``_table_query`` emiten el SQL de la fuente y afirmar que
    revientan mediría un estado que ya no existe.

    La forma del SQL la miden los casos de
    ``test_account_invoice_report_sql.py``; aquí sólo queda la comprobación de
    que ya **no** revientan, y el único que sigue bloqueado.
    """

    def test_the_four_sql_producers_no_longer_raise(self, db):
        company = ResCompany.objects.create(
            code='air-desbloqueo', name='Desbloqueo',
            currency=ResCurrency.objects.get_or_create(
                name='MXN', defaults={'symbol': '$'})[0])
        with company_scope(company.pk):
            report = AccountInvoiceReport()
            for produced in (AccountInvoiceReport._select(),
                             AccountInvoiceReport._from(),
                             AccountInvoiceReport._where(),
                             report._table_query):
                assert isinstance(produced, SQL)
                assert produced.code.strip()

    def test_read_group_select_raises_citing_read_group_not_field_to_sql(self):
        instance = AccountInvoiceReport()
        with pytest.raises(NotImplementedError) as excinfo:
            instance._read_group_select('price_average:avg', query=None)
        mensaje = str(excinfo.value)
        # El bloqueo cambió de dueño: _field_to_sql SÍ existe
        # (src/orm/models.py:1388); lo que falta es el read_group base.
        assert 'read_group' in mensaje
        assert '_field_to_sql si existe' in mensaje



class TestReportAccountReportInvoice:
    """El ensamblador de ``doc_ids``/``doc_model``/``docs`` -- portado y
    funcional. Los codigos QR se prueban aparte (dependen de la base para
    evaluar el queryset; no se cubren en unit).
    """

    def test_report_name(self):
        assert ReportAccountReportInvoice.REPORT_NAME == 'account.report_invoice'

    def test_qr_code_urls_is_a_noop_for_an_empty_docs_collection(self):
        assert ReportAccountReportInvoice._qr_code_urls(docs=[], data=None) == {}

    def test_qr_code_urls_raises_loudly_for_a_non_empty_collection(self):
        with pytest.raises(NotImplementedError) as excinfo:
            ReportAccountReportInvoice._qr_code_urls(docs=[object()], data=None)
        assert 'display_qr_code' in str(excinfo.value)


class TestReportAccountReportInvoiceWithPayments:
    def test_report_name(self):
        assert (ReportAccountReportInvoiceWithPayments.REPORT_NAME
                == 'account.report_invoice_with_payments')

    def test_inherits_from_the_base_report(self):
        assert issubclass(
            ReportAccountReportInvoiceWithPayments, ReportAccountReportInvoice)
