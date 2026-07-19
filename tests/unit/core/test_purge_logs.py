"""Tests unitarios — purge_logs (SOL-011 T-07, DEC-LOG-05).

Verifican la politica de retencion:
  - RequestLog > 30 d se purga; <= 30 d se conserva,
  - IrLogging INFO/DEBUG > 14 d se purga; WARNING/ERROR se conservan hasta 90 d,
  - BusinessEvent NUNCA se purga,
  - --dry-run cuenta pero no borra,
  - idempotente: segunda corrida purga 0.

``IrLogging`` (``ir.logging``, ``addons.base``) reemplaza a ``core.AppLog``
desde DEC-08 slice 2 — misma politica, otro modelo de origen.

created_at es auto_now_add → se fuerza con queryset.update para simular
antiguedad. Toca DB → django_db.
"""
from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from addons.base.models import IrLogging
from addons.observability.models import RequestLog
from addons.users.models import BusinessEvent

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def _age(model, pk, days):
    model.objects.filter(pk=pk).update(
        created_at=timezone.now() - timedelta(days=days))


def _run(*args):
    out = StringIO()
    call_command('purge_logs', *args, stdout=out)
    return out.getvalue()


def test_purges_old_requestlog_keeps_recent():
    old = RequestLog.objects.create(correlation_id='o', method='GET', path='/o',
                                    status_code=200, duration_ms=1)
    new = RequestLog.objects.create(correlation_id='n', method='GET', path='/n',
                                    status_code=200, duration_ms=1)
    _age(RequestLog, old.pk, 31)
    _age(RequestLog, new.pk, 29)
    _run()
    assert not RequestLog.objects.filter(pk=old.pk).exists()
    assert RequestLog.objects.filter(pk=new.pk).exists()


def test_applog_low_purged_at_14d_high_kept():
    info = IrLogging.objects.create(name='a', level='INFO', message='i')
    err = IrLogging.objects.create(name='a', level='ERROR', message='e')
    _age(IrLogging, info.pk, 15)   # INFO > 14 d -> purga
    _age(IrLogging, err.pk, 15)    # ERROR a 15 d -> se conserva (< 90 d)
    _run()
    assert not IrLogging.objects.filter(pk=info.pk).exists()
    assert IrLogging.objects.filter(pk=err.pk).exists()


def test_applog_high_purged_at_90d():
    err = IrLogging.objects.create(name='a', level='ERROR', message='e')
    _age(IrLogging, err.pk, 91)
    _run()
    assert not IrLogging.objects.filter(pk=err.pk).exists()


def test_does_not_touch_business_event():
    ev = BusinessEvent.objects.create(action=BusinessEvent.ACTION_ORDER_CREATED)
    _age(BusinessEvent, ev.pk, 400)
    _run()
    assert BusinessEvent.objects.filter(pk=ev.pk).exists()


def test_dry_run_counts_without_deleting():
    old = RequestLog.objects.create(correlation_id='o', method='GET', path='/o',
                                    status_code=200, duration_ms=1)
    _age(RequestLog, old.pk, 40)
    out = _run('--dry-run')
    assert 'dry-run' in out
    assert RequestLog.objects.filter(pk=old.pk).exists()


def test_idempotent_second_run_purges_zero():
    old = RequestLog.objects.create(correlation_id='o', method='GET', path='/o',
                                    status_code=200, duration_ms=1)
    _age(RequestLog, old.pk, 40)
    _run()
    out = _run()
    assert 'Total: 0 filas' in out
