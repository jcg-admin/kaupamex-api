"""
Tests — UC-FIN-05 proyeccion de flujo de caja (CashFlowProjection).

Proyeccion por **metodo directo** y **base percibido**: por sub-periodos
(``week``/``month``) sobre un horizonte, encadenando ``closing_balance`` de un
sub-periodo como ``opening_balance`` del siguiente (rolling), con multiplicador
por ``scenario`` (``base``/``optimistic``/``pessimistic``) y marca del primer
sub-periodo en deficit. Consultar/proyectar = ``finance.view``; guardar el
escenario = ``finance.edit`` (DEC-11).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model

import pytest

from addons.authz.models import (
    AccessLevel, Capability, Module, Role, RoleAssignment, RoleCapability,
)
from addons.finance.models import CashFlowProjection, ProjectionScenario

pytestmark = pytest.mark.integration

PROJ_URL = '/api/v2/finance/projection/'
COMPUTE_URL = PROJ_URL + 'compute/'

_VERB_LEVEL = {
    'view': AccessLevel.VIEW, 'create': AccessLevel.CREATE,
    'edit': AccessLevel.EDIT, 'full': AccessLevel.FULL,
}


def _user_with_caps(email, codes):
    role, _ = Role.objects.get_or_create(
        code=f'role_{"_".join(c.replace(".", "_") for c in codes)}',
        defaults={'name': 'Test finance role'},
    )
    for code in codes:
        noun, _, verb = code.partition('.')
        if verb in _VERB_LEVEL:
            target, level = noun, _VERB_LEVEL[verb]
        else:
            target, level = code, AccessLevel.FULL
        module, _ = Module.objects.get_or_create(
            code=target.split('.', 1)[0], defaults={'name': target},
        )
        cap, _ = Capability.objects.get_or_create(
            code=target, defaults={'module': module, 'name': target},
        )
        RoleCapability.objects.update_or_create(
            role=role, capability=cap, defaults={'level': level},
        )
    user = get_user_model().objects.create_user(email=email, password='TestPass123!')
    RoleAssignment.objects.create(user=user, role=role)
    return user


def _base_body(**over):
    body = {
        'scenario': 'base', 'horizon': 3, 'granularity': 'week',
        'opening_balance': '1000.00',
        'assumptions': {'income_per_period': '500.00',
                        'expense_per_period': '300.00', 'min_balance': '0.00'},
    }
    body.update(over)
    return body


class TestProjectionCompute:
    """UC-FIN-05 — proyectar (rolling directo, base percibido)."""

    def test_viewer_computes_rolling_projection(self, api_client, db):
        api_client.force_login(_user_with_caps('proj_v@practicayoruba.mx', ['finance.view']))
        res = api_client.post(COMPUTE_URL, _base_body(), format='json')
        assert res.status_code == 200, res.content
        periods = res.data['periods']
        assert len(periods) == 3
        # Rolling: opening=1000, +500 -300 = 1200; luego 1400; luego 1600.
        assert Decimal(periods[0]['closing_balance']) == Decimal('1200.00')
        assert Decimal(periods[1]['opening_balance']) == Decimal('1200.00')
        assert Decimal(periods[2]['closing_balance']) == Decimal('1600.00')
        assert res.data['deficit_index'] is None

    def test_optimistic_beats_base_income(self, api_client, db):
        api_client.force_login(_user_with_caps('proj_v2@practicayoruba.mx', ['finance.view']))
        base = api_client.post(COMPUTE_URL, _base_body(scenario='base'), format='json')
        opti = api_client.post(COMPUTE_URL, _base_body(scenario='optimistic'), format='json')
        assert Decimal(opti.data['periods'][0]['income']) > Decimal(base.data['periods'][0]['income'])

    def test_deficit_marks_first_subperiod_below_minimum(self, api_client, db):
        api_client.force_login(_user_with_caps('proj_v3@practicayoruba.mx', ['finance.view']))
        # opening 100, cada periodo -200 (income 0, expense 200) -> cierra -100 en periodo 0.
        body = _base_body(opening_balance='100.00', horizon=2,
                          assumptions={'income_per_period': '0.00',
                                       'expense_per_period': '200.00',
                                       'min_balance': '0.00'})
        res = api_client.post(COMPUTE_URL, body, format='json')
        assert res.status_code == 200, res.content
        assert res.data['deficit_index'] == 0

    def test_invalid_granularity_rejected(self, api_client, db):
        api_client.force_login(_user_with_caps('proj_v4@practicayoruba.mx', ['finance.view']))
        res = api_client.post(COMPUTE_URL, _base_body(granularity='daily'), format='json')
        assert res.status_code == 400, res.content


class TestProjectionScenarioPersistence:
    """UC-FIN-05 — guardar/consultar un escenario (finance.edit / view)."""

    def test_viewer_cannot_save_scenario(self, api_client, db):
        api_client.force_login(_user_with_caps('proj_v5@practicayoruba.mx', ['finance.view']))
        res = api_client.post(PROJ_URL, _base_body(), format='json')
        assert res.status_code == 403

    def test_editor_saves_scenario(self, api_client, db):
        api_client.force_login(_user_with_caps('proj_e@practicayoruba.mx', ['finance.edit']))
        res = api_client.post(PROJ_URL, _base_body(name='Q3 conservador'), format='json')
        assert res.status_code == 201, res.content
        assert res.data['created_by'] is not None
        proj = CashFlowProjection.objects.get(id=res.data['id'])
        assert proj.scenario == ProjectionScenario.BASE
        assert proj.name == 'Q3 conservador'

    def test_editor_retrieves_scenario_with_periods(self, api_client, db):
        editor = _user_with_caps('proj_e2@practicayoruba.mx', ['finance.edit'])
        proj = CashFlowProjection.objects.create(
            scenario=ProjectionScenario.BASE, horizon=2, granularity='week',
            opening_balance=Decimal('1000.00'), created_by=editor,
            assumptions={'income_per_period': '500.00',
                         'expense_per_period': '300.00', 'min_balance': '0.00'},
        )
        api_client.force_login(editor)
        res = api_client.get(f'{PROJ_URL}{proj.id}/')
        assert res.status_code == 200, res.content
        assert len(res.data['periods']) == 2
        assert Decimal(res.data['periods'][1]['closing_balance']) == Decimal('1400.00')
