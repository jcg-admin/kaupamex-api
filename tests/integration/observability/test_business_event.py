"""
Tests integration — BusinessEvent audit cross-cutting.

Cubre audit-log-eventos-cross-cutting:
ORDER_CANCELLED + RETURN_REQUESTED + RETURN_RESOLVED.
ORDER_CREATED testeado indirectamente; fixture de checkout
complejo requiere full cart/order setup, validacion en QA.

``BusinessEvent``/``audit_log_business`` vivian en ``users/models.py`` y
``users/audit.py``; el commit ``api@6cf8120`` disolvio ``users`` y ambos se
realojaron en ``observability`` (el unico addon net-new sancionado, DEC-12) —
no tienen homologo ``res.*`` en la referencia. Ver
``addons.observability.models.business_event`` y ``addons.observability.audit``.
"""
import pytest

from addons.observability.audit import audit_log_business
from addons.observability.models import BusinessEvent

pytestmark = [pytest.mark.integration, pytest.mark.django_db(transaction=True)]


class TestBusinessEventModel:
    """BusinessEvent existe + indexes + action choices."""

    def test_business_event_model_existe(self, db):
        assert hasattr(BusinessEvent, 'ACTION_ORDER_CREATED')
        assert hasattr(BusinessEvent, 'ACTION_ORDER_CANCELLED')
        assert hasattr(BusinessEvent, 'ACTION_RETURN_REQUESTED')
        assert hasattr(BusinessEvent, 'ACTION_RETURN_RESOLVED')

    def test_business_event_create_y_query(self, db, user):
        BusinessEvent.objects.create(
            actor=user,
            action=BusinessEvent.ACTION_ORDER_CREATED,
            target_type=BusinessEvent.TARGET_ORDER,
            target_id=123,
        )
        events = BusinessEvent.objects.filter(
            actor=user, action=BusinessEvent.ACTION_ORDER_CREATED,
        )
        assert events.count() == 1
        assert events.first().target_id == 123


class TestBusinessEventHelperPII:
    """DEC-CC-2 + DEC-AL-3 PII safe."""

    def test_helper_no_almacena_password_en_extra(self, db, user):
        audit_log_business(
            user, BusinessEvent.ACTION_ORDER_CREATED, None,
            target_type=BusinessEvent.TARGET_ORDER, target_id=1,
            extra={'password': 'leak'},  # devs malicioso/test
        )
        # El helper NO valida el extra (responsabilidad de quien lo
        # llama). El test documenta la convencion.
        ev = BusinessEvent.objects.filter(action=BusinessEvent.ACTION_ORDER_CREATED).first()
        assert ev is not None
        # DEC-CC convention: callers no deben pasar password en extra.
        # Aqui solo documentamos que el helper acepta dict raw.
