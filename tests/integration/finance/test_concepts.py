"""
Tests — UC-FIN-06 catalogo de conceptos de caja (CashConcept CRUD).

Primer slice del modulo financiero (MOD-028). Verifica el gate graduado
``finance`` (DEC-11): ``finance.view`` para listar, ``finance.edit`` para
crear/editar/desactivar, ``finance.full`` para borrar; mas la unicidad de
``code`` (DUPLICATE_CODE) y la inmutabilidad de ``code``/``kind`` (IMMUTABLE_FIELD).

Se usa un usuario NO-superadmin con exactamente las capacidades bajo prueba
para ejercer el resolver real (sin bypass de superadmin), igual que
``tests/integration/inventory/test_capability_gate.py``.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

import pytest

from apps.platform.authz.models import (
    AccessLevel, Capability, Module, Role, RoleAssignment, RoleCapability,
)
from apps.modules.finance.models import CashConcept, CashMovement

pytestmark = pytest.mark.integration

CONCEPTS_URL = '/api/v2/finance/concepts/'

_VERB_LEVEL = {
    'view': AccessLevel.VIEW, 'create': AccessLevel.CREATE,
    'edit': AccessLevel.EDIT, 'full': AccessLevel.FULL,
}


def _user_with_caps(email, codes):
    """Usuario NO-superadmin con exactamente las capacidades ``codes``.

    ``X.verbo`` graduado -> sustantivo ``X`` al nivel del verbo; una accion
    nombrada -> membresia a nivel FULL.
    """
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
    user = get_user_model().objects.create_user(
        email=email, password='TestPass123!',
    )
    RoleAssignment.objects.create(user=user, role=role)
    return user


class TestCashConceptCrud:
    """UC-FIN-06 — CRUD del catalogo de conceptos con gate graduado ``finance``."""

    def test_editor_creates_concept(self, api_client, db):
        editor = _user_with_caps('fin_editor@practicayoruba.mx', ['finance.edit'])
        api_client.force_login(editor)
        res = api_client.post(CONCEPTS_URL, {
            'code': 'FREIGHT_OUT', 'name': 'Flete al transportista',
            'kind': 'expense', 'account': '5101-01',
        }, format='json')
        assert res.status_code == 201, res.content
        assert res.data['code'] == 'FREIGHT_OUT'
        assert res.data['kind'] == 'expense'
        assert res.data['active'] is True

    def test_duplicate_code_conflicts(self, api_client, db):
        CashConcept.objects.create(code='SALES', name='Ventas', kind='income')
        editor = _user_with_caps('fin_editor2@practicayoruba.mx', ['finance.edit'])
        api_client.force_login(editor)
        res = api_client.post(CONCEPTS_URL, {
            'code': 'SALES', 'name': 'Ventas dup', 'kind': 'income',
        }, format='json')
        assert res.status_code == 409
        assert res.data['codigo_error'] == 'DUPLICATE_CODE'

    def test_code_is_immutable(self, api_client, db):
        concept = CashConcept.objects.create(
            code='COMMISSION', name='Comision gateway', kind='expense',
        )
        editor = _user_with_caps('fin_editor3@practicayoruba.mx', ['finance.edit'])
        api_client.force_login(editor)
        res = api_client.patch(
            f'{CONCEPTS_URL}{concept.id}/', {'code': 'COMMISSION_NEW'}, format='json',
        )
        assert res.status_code == 422
        assert res.data['codigo_error'] == 'IMMUTABLE_FIELD'

    def test_kind_is_immutable(self, api_client, db):
        concept = CashConcept.objects.create(
            code='REFUND', name='Reembolso', kind='expense',
        )
        editor = _user_with_caps('fin_editor4@practicayoruba.mx', ['finance.edit'])
        api_client.force_login(editor)
        res = api_client.patch(
            f'{CONCEPTS_URL}{concept.id}/', {'kind': 'income'}, format='json',
        )
        assert res.status_code == 422
        assert res.data['codigo_error'] == 'IMMUTABLE_FIELD'

    def test_editor_deactivates_concept(self, api_client, db):
        concept = CashConcept.objects.create(
            code='LEGACY', name='Concepto viejo', kind='income',
        )
        editor = _user_with_caps('fin_editor5@practicayoruba.mx', ['finance.edit'])
        api_client.force_login(editor)
        res = api_client.patch(
            f'{CONCEPTS_URL}{concept.id}/', {'active': False}, format='json',
        )
        assert res.status_code == 200
        assert res.data['active'] is False

    def test_viewer_can_list(self, api_client, db):
        CashConcept.objects.create(code='SALES2', name='Ventas', kind='income')
        viewer = _user_with_caps('fin_viewer@practicayoruba.mx', ['finance.view'])
        api_client.force_login(viewer)
        res = api_client.get(CONCEPTS_URL)
        assert res.status_code == 200

    def test_viewer_cannot_create(self, api_client, db):
        # finance.view NO alcanza para crear (exige finance.edit).
        viewer = _user_with_caps('fin_viewer2@practicayoruba.mx', ['finance.view'])
        api_client.force_login(viewer)
        res = api_client.post(CONCEPTS_URL, {
            'code': 'NEW_ONE', 'name': 'Nuevo', 'kind': 'income',
        }, format='json')
        assert res.status_code == 403

    def test_filter_by_kind(self, api_client, db):
        CashConcept.objects.create(code='IN1', name='In', kind='income')
        CashConcept.objects.create(code='EX1', name='Ex', kind='expense')
        viewer = _user_with_caps('fin_viewer3@practicayoruba.mx', ['finance.view'])
        api_client.force_login(viewer)
        res = api_client.get(f'{CONCEPTS_URL}?kind=expense')
        assert res.status_code == 200
        items = res.data['results'] if isinstance(res.data, dict) else res.data
        codes = [c['code'] for c in items]
        assert 'EX1' in codes and 'IN1' not in codes

    def test_delete_unused_concept(self, api_client, db):
        concept = CashConcept.objects.create(code='UNUSED', name='Sin uso', kind='income')
        admin = _user_with_caps('fin_full@practicayoruba.mx', ['finance.full'])
        api_client.force_login(admin)
        res = api_client.delete(f'{CONCEPTS_URL}{concept.id}/')
        assert res.status_code == 204
        assert not CashConcept.objects.filter(id=concept.id).exists()

    def test_delete_concept_in_use_conflicts(self, api_client, db):
        # H-API-FIN-01 cerrado: un concepto con movimiento no se puede borrar.
        concept = CashConcept.objects.create(code='USED', name='En uso', kind='income')
        CashMovement.objects.create(
            concept=concept, kind='income', amount=Decimal('10.00'),
            occurred_at=timezone.now(),
        )
        admin = _user_with_caps('fin_full2@practicayoruba.mx', ['finance.full'])
        api_client.force_login(admin)
        res = api_client.delete(f'{CONCEPTS_URL}{concept.id}/')
        assert res.status_code == 409
        assert res.data['codigo_error'] == 'CONCEPT_IN_USE'
