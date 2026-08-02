"""Tests unitarios — inmutabilidad append-only de BusinessEvent (SOL-011 T-10).

BusinessEvent hereda de AppendOnlyModel (DEC-LOG-10): el INSERT inicial (siempre
via objects.create) es permitido, pero un UPDATE de instancia o un delete() de
instancia lanzan PermissionError. Las operaciones bulk siguen permitidas. El
auto-stamp de correlation_id (DEC-LOG-07) en save() debe seguir funcionando en el
INSERT.

Toca DB -> django_db.
"""
import pytest

from addons.observability.models import BusinessEvent

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def _make():
    return BusinessEvent.objects.create(
        action=BusinessEvent.ACTION_ORDER_CREATED,
        target_type=BusinessEvent.TARGET_ORDER, target_id=1)


def test_insert_allowed():
    ev = _make()
    assert ev.pk is not None
    assert BusinessEvent.objects.filter(pk=ev.pk).exists()


def test_update_instance_blocked():
    ev = _make()
    ev.target_id = 999
    with pytest.raises(PermissionError):
        ev.save()
    assert BusinessEvent.objects.get(pk=ev.pk).target_id == 1


def test_instance_delete_blocked():
    ev = _make()
    with pytest.raises(PermissionError):
        ev.delete()
    assert BusinessEvent.objects.filter(pk=ev.pk).exists()


def test_bulk_delete_allowed():
    ev = _make()
    deleted, _ = BusinessEvent.objects.filter(pk=ev.pk).delete()
    assert deleted == 1
    assert not BusinessEvent.objects.filter(pk=ev.pk).exists()


def test_correlation_id_autostamp_still_works(monkeypatch):
    # DEC-LOG-07: en el INSERT, save() sella el correlation_id del contexto si el
    # llamador no lo fijo. El guard append-only no debe interferir con eso.
    monkeypatch.setattr(
        'addons.users.models.get_correlation_id', lambda: 'abc123corr')
    ev = BusinessEvent.objects.create(action=BusinessEvent.ACTION_ORDER_CANCELLED)
    assert ev.correlation_id == 'abc123corr'
    assert BusinessEvent.objects.get(pk=ev.pk).correlation_id == 'abc123corr'


def test_explicit_correlation_id_not_overwritten(monkeypatch):
    monkeypatch.setattr(
        'addons.users.models.get_correlation_id', lambda: 'ctx-value')
    ev = BusinessEvent.objects.create(
        action=BusinessEvent.ACTION_ORDER_CREATED, correlation_id='explicit')
    assert ev.correlation_id == 'explicit'
