"""Tests unitarios — inmutabilidad append-only de los logs (SOL-011).

Precedente adaptado de CNST-009 (otro proyecto): los carriers de logging
declaran ser append-only (docstring + endpoint read-only 405), pero hasta
ahora nada lo imponia a nivel de modelo. Estos tests fijan el contrato:

  - INSERT inicial permitido (el middleware / handler crean filas),
  - UPDATE de instancia bloqueado (``save`` sobre fila existente -> PermissionError),
  - DELETE de instancia bloqueado (``obj.delete()`` -> PermissionError),
  - ``QuerySet.delete()`` bulk SIGUE permitido (lo usa ``purge_logs``, DEC-LOG-05),
  - ``QuerySet.update()`` bulk SIGUE permitido (no pasa por ``save`` de instancia).

Toca DB -> django_db.
"""
import pytest

from core.models import AppLog, RequestLog

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def _make_requestlog():
    return RequestLog.objects.create(
        correlation_id='cid-rl', method='GET', path='/x',
        status_code=200, duration_ms=1)


def _make_applog():
    return AppLog.objects.create(
        logger_name='apps.x', level=AppLog.LEVEL_INFO, msg='hola')


# --- INSERT permitido -------------------------------------------------------

def test_requestlog_insert_allowed():
    row = _make_requestlog()
    assert row.pk is not None
    assert RequestLog.objects.filter(pk=row.pk).exists()


def test_applog_insert_allowed():
    row = _make_applog()
    assert row.pk is not None
    assert AppLog.objects.filter(pk=row.pk).exists()


# --- UPDATE de instancia bloqueado -----------------------------------------

def test_requestlog_update_blocked():
    row = _make_requestlog()
    row.status_code = 500
    with pytest.raises(PermissionError):
        row.save()
    # DB intacta: el guard corta antes del UPDATE.
    assert RequestLog.objects.get(pk=row.pk).status_code == 200


def test_applog_update_blocked():
    row = _make_applog()
    row.msg = 'modificado'
    with pytest.raises(PermissionError):
        row.save()
    assert AppLog.objects.get(pk=row.pk).msg == 'hola'


# --- DELETE de instancia bloqueado -----------------------------------------

def test_requestlog_instance_delete_blocked():
    row = _make_requestlog()
    with pytest.raises(PermissionError):
        row.delete()
    assert RequestLog.objects.filter(pk=row.pk).exists()


def test_applog_instance_delete_blocked():
    row = _make_applog()
    with pytest.raises(PermissionError):
        row.delete()
    assert AppLog.objects.filter(pk=row.pk).exists()


# --- Operaciones bulk SIGUEN permitidas (purge_logs / retencion) -----------

def test_requestlog_bulk_delete_allowed():
    row = _make_requestlog()
    deleted, _ = RequestLog.objects.filter(pk=row.pk).delete()
    assert deleted == 1
    assert not RequestLog.objects.filter(pk=row.pk).exists()


def test_applog_bulk_delete_allowed():
    row = _make_applog()
    deleted, _ = AppLog.objects.filter(pk=row.pk).delete()
    assert deleted == 1
    assert not AppLog.objects.filter(pk=row.pk).exists()


def test_requestlog_bulk_update_allowed():
    row = _make_requestlog()
    RequestLog.objects.filter(pk=row.pk).update(status_code=204)
    assert RequestLog.objects.get(pk=row.pk).status_code == 204
