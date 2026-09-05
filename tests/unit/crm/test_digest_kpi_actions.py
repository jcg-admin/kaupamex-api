"""``crm/models/digest.py::_compute_kpis_actions`` — el gancho de acciones
que ``crm`` cuelga sobre ``digest.digest`` (tarea #158).

Adaptación de ``odoo19c: addons/crm/models/digest.py:33-38`` (LGPL-3) —
atribución y aviso de licencia preservados (DEC-KX-03).

Prueba la función de módulo **directamente** (no a través de la cadena
completa instalada sobre ``DigestDigest`` — eso lo cubre
``tests/unit/digest/test_digest_kpi_actions.py``), con un ``previous``
doble de prueba: aísla la lógica propia de ``crm`` de lo que la base o
``hr_recruitment`` aporten.
"""
import pytest

from addons.base.models.ir_model import IrModelData
from addons.base.models.res_groups import ResGroups
from addons.crm.models.digest import (
    ACTION_ALL_LEADS, ACTION_PIPELINE, GROUP_USE_LEAD, _compute_kpis_actions,
)
from tests.factories.user_factory import UserFactory

pytestmark = pytest.mark.django_db


def _previous(seed=None):
    """Un ``previous`` doble de prueba — mismo contrato que el
    ``_compute_kpis_actions`` base: recibe ``(company, user)`` y devuelve
    un diccionario. Cada llamada construye uno **nuevo** a partir de
    ``seed``, para que un test no contamine al siguiente reutilizando el
    mismo objeto mutable.
    """
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

    def test_mutates_and_returns_the_previous_dict(self):
        """Discriminante de forma: la fuente muta el diccionario que
        ``super()`` devolvió y lo retorna — no construye uno propio. Si el
        override devolviera una copia en vez de mutar ``previous()``, este
        test caería (``res is seed`` sería falso)."""
        seed = {}
        res = _compute_kpis_actions(
            None, lambda company, user: seed, None, None)
        assert res is seed
        assert 'kpi_crm_lead_created' in seed


class TestDefaultActions:
    def test_both_kpis_point_to_the_pipeline_by_default(self):
        user = UserFactory(login='vendedor@kaupamex.mx')
        res = _compute_kpis_actions(None, _previous(), None, user)
        assert res['kpi_crm_lead_created'] == ACTION_PIPELINE
        assert res['kpi_crm_opportunities_won'] == ACTION_PIPELINE


class TestGroupUseLeadBranch:
    """≙ ``if user.has_group('crm.group_use_lead'): ...`` (``:36-37``)."""

    @pytest.fixture
    def lead_group(self):
        group = ResGroups.objects.create(name='Usa leads')
        IrModelData.set_xmlid(group, GROUP_USE_LEAD)
        return group

    def test_switches_lead_action_when_user_has_the_group(self, lead_group):
        user = UserFactory(login='lead-user@kaupamex.mx')
        user.group_ids.add(lead_group)
        res = _compute_kpis_actions(None, _previous(), None, user)
        assert res['kpi_crm_lead_created'] == ACTION_ALL_LEADS

    def test_opportunities_action_never_switches(self, lead_group):
        """Discriminante: sólo ``kpi_crm_lead_created`` depende del grupo.
        Si el código condicionara las DOS claves por error, esto caería."""
        user = UserFactory(login='lead-user-2@kaupamex.mx')
        user.group_ids.add(lead_group)
        res = _compute_kpis_actions(None, _previous(), None, user)
        assert res['kpi_crm_opportunities_won'] == ACTION_PIPELINE

    def test_does_not_switch_without_the_group(self):
        user = UserFactory(login='sin-grupo@kaupamex.mx')
        res = _compute_kpis_actions(None, _previous(), None, user)
        assert res['kpi_crm_lead_created'] == ACTION_PIPELINE

    def test_switch_survives_an_unrelated_group(self, lead_group):
        """Discriminante de instrumento: un usuario con OTRO grupo (no
        ``group_use_lead``) no debe activar la rama — un ``has_group`` mal
        implementado que devolviera ``True`` para cualquier grupo no lo
        detectaría."""
        other = ResGroups.objects.create(name='Otro grupo cualquiera')
        IrModelData.set_xmlid(other, 'crm.group_otro_cualquiera')
        user = UserFactory(login='otro-grupo@kaupamex.mx')
        user.group_ids.add(other)
        res = _compute_kpis_actions(None, _previous(), None, user)
        assert res['kpi_crm_lead_created'] == ACTION_PIPELINE


class TestNoUserIsFailClosed:
    def test_none_user_does_not_raise(self):
        res = _compute_kpis_actions(None, _previous(), None, None)
        assert res['kpi_crm_lead_created'] == ACTION_PIPELINE
        assert res['kpi_crm_opportunities_won'] == ACTION_PIPELINE
