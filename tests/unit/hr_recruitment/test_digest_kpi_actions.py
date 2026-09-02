"""``hr_recruitment/models/digest.py::_compute_kpis_actions`` — el gancho de
acciones que ``hr_recruitment`` cuelga sobre ``digest.digest`` (tarea #158).

Adaptación de ``odoo19c: addons/hr_recruitment/models/digest.py:19-22``
(LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Prueba la función de módulo directamente, con un ``previous`` doble de
prueba — la cadena completa (base + ``crm`` + ``hr_recruitment``, tal como
Django la instala) la cubre
``tests/unit/digest/test_digest_kpi_actions.py``. Sin fixtures de DB: a
diferencia de ``crm``, esta acción no depende de grupos ni de ``user``.
"""
from addons.hr_recruitment.models.digest import (
    ACTION_OPEN_MY_EMPLOYEES, _compute_kpis_actions,
)


def _previous(seed=None):
    """Mismo doble de prueba que ``tests/unit/crm/test_digest_kpi_actions``."""
    def previous(company, user):
        return dict(seed or {})
    return previous


class TestChainsWithThePrevious:
    """≙ ``res = super()._compute_kpis_actions(company, user)``."""

    def test_keeps_whatever_the_previous_link_already_set(self):
        res = _compute_kpis_actions(
            None, _previous({'kpi_other_addon': 'other.action'}), None, None,
        )
        assert res['kpi_other_addon'] == 'other.action'
        assert res['kpi_hr_recruitment_new_colleagues'] == (
            ACTION_OPEN_MY_EMPLOYEES)

    def test_mutates_and_returns_the_previous_dict(self):
        """Discriminante de forma, mismo criterio que ``crm``: si el
        override devolviera una copia en vez de mutar lo que ``previous()``
        entregó, ``res is seed`` sería falso."""
        seed = {}
        res = _compute_kpis_actions(
            None, lambda company, user: seed, None, None)
        assert res is seed


class TestAction:
    def test_always_points_to_open_my_employees(self):
        """No hay condición de grupo en la fuente — a diferencia de
        ``crm``, la acción es constante independientemente de ``user``."""
        res = _compute_kpis_actions(None, _previous(), None, None)
        assert res['kpi_hr_recruitment_new_colleagues'] == (
            ACTION_OPEN_MY_EMPLOYEES)

    def test_action_is_the_unresolved_xmlid_not_a_url(self):
        """Discriminante de forma: nunca lleva ``?menu_id=`` — la
        divergencia declarada en el docstring del módulo (sin cliente web
        de Odoo, no hay menú que resolver)."""
        res = _compute_kpis_actions(None, _previous(), None, None)
        assert '?' not in res['kpi_hr_recruitment_new_colleagues']
