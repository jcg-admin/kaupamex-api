"""Tests unitarios — BusinessEvent.correlation_id (SOL-011 T-05, DEC-LOG-07).

Verifican que ``BusinessEvent.save()`` sella el ``correlation_id`` de la request
en curso para poder unir el evento de negocio con ``RequestLog`` / ``AppLog``:
  - autopopula desde el contexto de logging cuando no se provee,
  - vacio fuera de un request (management commands / cron),
  - no pisa un ``correlation_id`` provisto explicitamente.

Toca DB (BusinessEvent) → django_db.
"""
import pytest

from apps.core.logging_context import clear_correlation_id, set_correlation_id
from apps.modules.users.models import BusinessEvent

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def test_stamps_correlation_id_from_context():
    set_correlation_id('abc123def456')
    try:
        ev = BusinessEvent.objects.create(action=BusinessEvent.ACTION_ORDER_CREATED)
        assert ev.correlation_id == 'abc123def456'
    finally:
        clear_correlation_id()


def test_empty_correlation_id_outside_request():
    clear_correlation_id()
    ev = BusinessEvent.objects.create(action=BusinessEvent.ACTION_ORDER_CANCELLED)
    assert ev.correlation_id == ''


def test_explicit_correlation_id_not_overwritten():
    set_correlation_id('context-value')
    try:
        ev = BusinessEvent.objects.create(
            action=BusinessEvent.ACTION_RETURN_REQUESTED,
            correlation_id='explicit-value',
        )
        assert ev.correlation_id == 'explicit-value'
    finally:
        clear_correlation_id()
