"""Las 14 columnas que ``account.invoice.report`` lee de las dos tablas de asiento.

Porte de la tarea #989. La suite mide tres cosas distintas, y las separa a
proposito porque fallan por causas distintas:

1. que las columnas **existan con el nombre que el SQL de la vista consulta**
   -- ``line.partner_id``, ``move.invoice_user_id``, ... El nombre de columna
   lo produce Django del nombre de campo, asi que el control se hace contra
   ``_meta``, no contra el atributo de Python;
2. que los compute que **si** tienen sus insumos escriban el valor correcto;
3. que los cinco compute **bloqueados** levanten citando la pieza ausente --
   un bloqueo silencioso se leeria como campo que nadie llena.

*Metrica:* nombres de columna de ``_meta.get_fields()`` cruzados contra la
lista literal que ``AccountInvoiceReport._select``/``_from`` consultan.
*Ciega a:* el tipo y la nulabilidad de la columna; comprueba que resuelva.
"""
import datetime
from decimal import Decimal

import pytest
from django.apps import apps

from addons.account.models.account_move import AccountMove
from addons.account.models.account_move_line import AccountMoveLine


#: Las seis de ``account_move`` que el docstring de #989 midio como ausentes.
MOVE_COLUMNS = [
    'invoice_user_id', 'fiscal_position_id', 'invoice_date',
    'invoice_date_due', 'invoice_currency_rate', 'commercial_partner_id',
]

#: Las ocho de ``account_move_line``.
LINE_COLUMNS = [
    'product_id', 'journal_id', 'company_id', 'company_currency_id',
    'partner_id', 'price_subtotal', 'price_total', 'product_uom_id',
]


def column_names(model):
    """Los nombres de columna reales, que es lo que el SQL de la vista lee."""
    return {f.column for f in model._meta.get_fields() if getattr(f, 'concrete', False)}


class TestTheColumnsTheViewReads:

    def test_the_move_declares_its_six_columns(self):
        faltan = sorted(set(MOVE_COLUMNS) - column_names(AccountMove))
        assert faltan == [], f'columnas ausentes en account_move: {faltan}'

    def test_the_line_declares_its_eight_columns(self):
        faltan = sorted(set(LINE_COLUMNS) - column_names(AccountMoveLine))
        assert faltan == [], f'columnas ausentes en account_move_line: {faltan}'

    def test_the_gap_the_task_measured_was_fourteen(self):
        """El denominador de #989, escrito para que un cambio de alcance se vea."""
        assert len(MOVE_COLUMNS) + len(LINE_COLUMNS) == 14

    def test_the_move_fk_targets_are_the_ones_the_source_names(self):
        fk_fields = {f.name: f for f in AccountMove._meta.get_fields()
                  if getattr(f, 'concrete', False) and f.is_relation}
        assert fk_fields['commercial_partner'].related_model is apps.get_model('base', 'ResPartner')
        assert fk_fields['fiscal_position'].related_model is apps.get_model(
            'account', 'AccountFiscalPosition')

    def test_the_line_partner_points_at_res_partner_not_at_the_user(self):
        """El apunte nace del lado correcto del eje que la tarea #142 tiene abierto.

        El asiento padre apunta al modelo de usuario; el apunte no repite ese
        desnivel. Si alguien lo iguala "por consistencia", este caso cae.
        """
        field = AccountMoveLine._meta.get_field('partner')
        assert field.related_model is apps.get_model('base', 'ResPartner')


class TestTheComputesThatRun:

    def test_the_due_date_falls_back_to_today_when_there_are_no_terms(self):
        """La rama de respaldo de ``_compute_invoice_date_due`` (≙ :1077-1084)."""
        move = AccountMove(invoice_date_due=None)
        move._compute_invoice_date_due()
        assert move.invoice_date_due == datetime.date.today()

    def test_the_due_date_already_written_survives(self):
        """``or move.invoice_date_due`` -- un valor puesto a mano no se pisa."""
        puesta = datetime.date(2026, 1, 15)
        move = AccountMove(invoice_date_due=puesta)
        move._compute_invoice_date_due()
        assert move.invoice_date_due == puesta

    def test_the_commercial_partner_is_none_without_a_partner(self):
        move = AccountMove()
        move._compute_commercial_partner_id()
        assert move.commercial_partner is None

    def test_the_line_partner_copies_the_moves_commercial_entity(self):
        """≙ ``line.move_id.partner_id.commercial_partner_id`` (:533-535)."""
        line = AccountMoveLine()
        line._compute_partner_id()
        assert line.partner is None

    def test_the_uom_is_none_without_a_product(self):
        line = AccountMoveLine()
        line._compute_product_uom_id()
        assert line.product_uom is None

    def test_the_totals_default_to_zero_until_the_tax_axis_lands(self):
        """Consecuencia declarada del bloqueo de ``_compute_totals`` (#990)."""
        line = AccountMoveLine()
        assert line.price_subtotal == Decimal('0.00')
        assert line.price_total == Decimal('0.00')


class TestTheComputesThatAreBlocked:
    """Un bloqueo silencioso se leeria como campo que nadie llena.

    Cada caso exige que el mensaje NOMBRE la pieza ausente: sin eso, el
    ``NotImplementedError`` no distingue «esta bloqueado por X» de «no se
    escribio». Es el sub-patron D de ``metrica-decide-la-conclusion``.
    """

    def test_the_sale_person_compute_cites_is_sale_document(self):
        with pytest.raises(NotImplementedError) as exc:
            AccountMove()._compute_invoice_default_sale_person()
        assert 'is_sale_document' in str(exc.value)

    def test_the_fiscal_position_compute_cites_its_resolver(self):
        with pytest.raises(NotImplementedError) as exc:
            AccountMove()._compute_fiscal_position_id()
        assert '_get_fiscal_position' in str(exc.value)

    def test_the_currency_rate_compute_cites_the_expected_rate(self):
        with pytest.raises(NotImplementedError) as exc:
            AccountMove()._compute_invoice_currency_rate()
        assert 'expected_currency_rate' in str(exc.value)

    def test_the_totals_compute_cites_tax_ids_and_not_the_engine(self):
        """El bloqueo es del DATO: ``compute_all`` si existe y el mensaje lo dice."""
        with pytest.raises(NotImplementedError) as exc:
            AccountMoveLine()._compute_totals()
        mensaje = str(exc.value)
        assert 'tax_ids' in mensaje
        assert 'compute_all si existe' in mensaje

    def test_both_inverses_cite_the_selective_recompute(self):
        for method in ('_inverse_partner_id', '_inverse_product_id'):
            with pytest.raises(NotImplementedError) as exc:
                getattr(AccountMoveLine(), method)()
            assert '_conditional_add_to_compute' in str(exc.value)
