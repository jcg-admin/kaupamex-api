"""``account`` sobre ``account.analytic.line`` (tarea #398, tramo 2).

Los 11 símbolos de la referencia (odoo19c:
``account/models/account_analytic_line.py``) están BLOQUEADOS — ver el
docstring de ``account_analytic_line.py``. Igual que
``test_account_analytic_account.py``: no hay comportamiento portado que
probar, así que se verifica que la causa raíz del bloqueo (``move_line_id``
ausente en ``account.analytic.line``, y ``partner``/``journal`` ausentes en
``account.move.line``) sigue siendo cierta.
"""
import pytest

from addons.account.models.account_analytic_line import (
    apply_account_analytic_line_extensions,
)
from addons.account.models.account_move_line import AccountMoveLine
from addons.analytic.models import AccountAnalyticLine

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


class TestTheNoOpIsSafe:
    def test_it_does_not_raise_and_returns_none(self):
        assert apply_account_analytic_line_extensions() is None

    def test_it_adds_no_field_to_the_analytic_line(self):
        before = {f.name for f in AccountAnalyticLine._meta.get_fields()}
        apply_account_analytic_line_extensions()
        after = {f.name for f in AccountAnalyticLine._meta.get_fields()}
        assert before == after
        assert 'move_line' not in after
        assert 'general_account' not in after
        assert 'journal' not in after


class TestThePremiseOfTheBlockIsStillTrue:
    def test_analytic_line_has_no_move_line_field(self):
        names = {f.name for f in AccountAnalyticLine._meta.get_fields()}
        assert 'move_line' not in names
        assert 'move_line_id' not in names

    def test_account_move_line_has_no_partner_nor_journal_field(self):
        """Doble bloqueo de ``_compute_partner_id``/``journal_id`` — ver
        docstring del archivo: aunque ``move_line`` existiera, estos dos
        tampoco están en el destino."""
        names = {f.name for f in AccountMoveLine._meta.get_fields()}
        assert 'partner' not in names
        assert 'journal' not in names

    def test_account_analytic_line_already_has_category_and_amount(self):
        """La mitad que NO bloquea: ``category``/``amount`` existen en la
        base (necesarios para ``_compute_analytic_profitability`` si el
        bloqueo se levantara), pero sin ``general_account`` el cómputo no
        tiene de dónde leer ``account_type`` — el bloqueo real."""
        names = {f.name for f in AccountAnalyticLine._meta.get_fields()}
        assert 'category' in names
        assert 'amount' in names
