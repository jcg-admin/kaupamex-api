"""Tests unitarios — ``purge_logs`` (SOL-011 T-07, DEC-LOG-05).

Verifican la politica de retencion sobre su **unico sujeto vivo**:

- ``IrLogging`` INFO/DEBUG > 14 d se purga; WARNING/ERROR se conservan hasta 90 d,
- ``BusinessEvent`` NUNCA se purga,
- ``--dry-run`` cuenta pero no borra,
- idempotente: segunda corrida purga 0.

**Reescritos con DEC-AF-11.** ``purge_expired`` cubria dos modelos y vivia en
``RequestLog``; retirado ese modelo —su mitad de acceso es trabajo del
``access_log`` del proxy inverso— queda un solo sujeto y el metodo se mudo a
``IrLogging``. Los cuatro casos que asertaban sobre la ventana de 30 dias de
``RequestLog`` desaparecen con el: no hay ventana intermedia, un 4xx vive hoy
90 dias como ``WARNING`` (consecuencia declarada, tarea #616).

El archivo vive aqui porque el sujeto del test —el **comando**— se mudo con su
modelo al disolverse ``observability`` (H-API-752). La politica que el comando
invoca tiene su propio test en ``tests/unit/base/test_ir_logging.py``.

``created_at`` es ``auto_now_add`` → se fuerza con ``queryset.update`` para
simular antiguedad. Toca DB → ``django_db``.
"""
from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from addons.base.models import IrLogging
from addons.observability.models import BusinessEvent

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def _age(model, pk, days):
    model.objects.filter(pk=pk).update(
        created_at=timezone.now() - timedelta(days=days))


def _run(*args):
    out = StringIO()
    call_command('purge_logs', *args, stdout=out)
    return out.getvalue()


def test_low_level_purged_at_14d_high_kept():
    info = IrLogging.objects.create(name='a', level='INFO', message='i')
    err = IrLogging.objects.create(name='a', level='ERROR', message='e')
    _age(IrLogging, info.pk, 15)   # INFO > 14 d -> purga
    _age(IrLogging, err.pk, 15)    # ERROR a 15 d -> se conserva (< 90 d)
    _run()
    assert not IrLogging.objects.filter(pk=info.pk).exists()
    assert IrLogging.objects.filter(pk=err.pk).exists()


def test_high_level_purged_at_90d():
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
    info = IrLogging.objects.create(name='a', level='INFO', message='i')
    _age(IrLogging, info.pk, 40)
    out = _run('--dry-run')
    assert 'dry-run' in out
    assert IrLogging.objects.filter(pk=info.pk).exists()


def test_idempotent_second_run_purges_zero():
    info = IrLogging.objects.create(name='a', level='INFO', message='i')
    _age(IrLogging, info.pk, 40)
    _run()
    out = _run()
    assert 'Total: 0 filas' in out
