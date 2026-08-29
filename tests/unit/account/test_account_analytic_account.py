"""``account`` sobre ``account.analytic.account`` (tarea #520).

Los 4 símbolos de la referencia (odoo19c:
``account/models/account_analytic_account.py``) siguen BLOQUEADOS — ver el
docstring de ``account_analytic_account.py``: el conector ``move_line`` que
se construyó en esta tarea (``account_analytic_line.py``) no alcanza a este
archivo, porque su bloqueo es ``AccountMove.get_sale_types``/
``get_purchase_types`` y ``AccountMoveLine.analytic_distribution`` — ninguno
de los dos vive en un archivo que esta tarea pueda escribir. Este test no
verifica comportamiento portado (no hay ninguno): verifica que el bloqueo
sigue siendo cierto, para que este archivo no quede desactualizado en
silencio si algún día las dos piezas aparecen.
"""
import inspect

import pytest

from addons.account.models.account_analytic_account import apply_account_extensions
from addons.account.models.account_move import AccountMove
from addons.account.models.account_move_line import AccountMoveLine
from addons.analytic.models import AccountAnalyticAccount

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


class TestTheNoOpIsSafe:
    def test_it_does_not_raise_and_returns_none(self):
        assert apply_account_extensions() is None

    def test_it_adds_no_field_to_the_analytic_account(self):
        """El no-op es literal: cero superficie nueva sobre el modelo base."""
        before = {f.name for f in AccountAnalyticAccount._meta.get_fields()}
        apply_account_extensions()
        after = {f.name for f in AccountAnalyticAccount._meta.get_fields()}
        assert before == after
        assert 'invoice_count' not in after
        assert 'vendor_bill_count' not in after


class TestThePremiseOfTheBlockIsStillTrue:
    """Un bloqueador cayó y el otro sigue: los dos casos lo miden por separado.

    El archivo bloqueado citaba DOS piezas ausentes. Los predicados de tipo de
    asiento se portaron (``account_move.py``, ≙ ``odoo19c: :6468-6506``), así
    que ese caso mide ahora su PRESENCIA. El que sigue vivo es
    ``analytic_distribution``, y es el que mantiene el bloqueo — tarea #526.
    """

    def test_the_move_type_predicates_are_no_longer_missing(self):
        """Reescrito, no ajustado: antes exigía su ausencia."""
        names = {name for name, _ in inspect.getmembers(AccountMove)}
        assert 'get_sale_types' in names
        assert 'get_purchase_types' in names
        assert AccountMove.get_sale_types(True)[-1] == 'out_receipt'

    def test_account_move_line_has_no_analytic_distribution_field(self):
        """El bloqueador que SIGUE en pie — el único de los dos."""
        names = {f.name for f in AccountMoveLine._meta.get_fields()}
        assert 'analytic_distribution' not in names

    def test_account_move_still_declares_sale_and_purchase_move_types(self):
        """La mitad que NO bloquea: los tipos existen, sólo faltan los
        clasificadores (que este archivo no reconstruye por sí solo — ver su
        docstring: el bloqueo real es el enlace analítico, no esto)."""
        move_types = {value for value, _ in AccountMove.MOVE_TYPES}
        assert {'out_invoice', 'out_refund', 'out_receipt'} <= move_types
        assert {'in_invoice', 'in_refund', 'in_receipt'} <= move_types
