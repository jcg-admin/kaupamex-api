"""El volcado escribe columnas: ni la lógica de ``save()`` ni las señales.

≙ ``_flush`` → ``_write_multi`` (``odoo19c: odoo/orm/models.py:4520-4526``,
*"Low-level implementation of write()"*): un ``UPDATE`` de las columnas
sucias más ``write_date``/``write_uid`` (log access). La lógica de negocio —y
con ella las automatizaciones de escritura— vive en ``write``/``create``, no
en el volcado. Aquí la lógica de negocio de una fila de Django vive también
en los receptores de ``pre_save``/``post_save`` (``base_automation``
escucha todos los modelos), así que volcar por ``save()`` o por
``save_base()`` la ejecutaba en cada volcado. designs/flush-writes-columns.md.
"""
from datetime import datetime
from datetime import timezone as dt_timezone
from decimal import Decimal

import pytest
from django.db.models.signals import post_save, pre_save

from addons.crm.models import CrmLead
from orm.environments import env as current_env
from orm.environments import transaction_scope

pytestmark = pytest.mark.django_db


def _flush():
    with transaction_scope():
        current_env().flush_all()


@pytest.fixture
def lead():
    record = CrmLead.objects.create(name='Iniciativa', probability=40,
                                    expected_revenue=Decimal('1000'))
    _flush()
    return record


@pytest.fixture
def signals_seen():
    seen = []

    def listen(sender, instance, **kwargs):
        if sender is CrmLead:
            seen.append(kwargs.get('signal'))

    pre_save.connect(listen, weak=False, dispatch_uid='flush-contract-pre')
    post_save.connect(listen, weak=False, dispatch_uid='flush-contract-post')
    yield seen
    pre_save.disconnect(dispatch_uid='flush-contract-pre')
    post_save.disconnect(dispatch_uid='flush-contract-post')


def test_the_flush_emits_no_save_signals(lead, signals_seen):
    """Un recálculo pendiente se vuelca sin ``pre_save``/``post_save``."""
    lead.expected_revenue = Decimal('2000')
    lead.save(update_fields=['expected_revenue'])
    signals_seen.clear()
    _flush()
    assert CrmLead.objects.values_list(
        'prorated_revenue', flat=True).get(pk=lead.pk) == pytest.approx(800.0)
    assert signals_seen == []


def test_the_flush_runs_no_save_override(lead, monkeypatch):
    calls = []
    original = CrmLead.save

    def counting(self, *args, **kwargs):
        calls.append(kwargs.get('update_fields'))
        return original(self, *args, **kwargs)

    lead.expected_revenue = Decimal('3000')
    lead.save(update_fields=['expected_revenue'])
    monkeypatch.setattr(CrmLead, 'save', counting)
    _flush()
    assert calls == []


def test_the_flush_stamps_the_write_date(lead):
    """El volcado sella ``write_date`` con la hora de la transacción.

    Dentro de una transacción ``cr.now()`` no se mueve, así que comparar con
    la fecha anterior no discrimina. Se envejece la columna en la tabla
    después del ``save`` y antes del volcado: el escritor relee la fila, y
    sólo ``Field.pre_save`` vuelve a poner la hora de la transacción.
    """
    lead.expected_revenue = Decimal('4000')
    lead.save(update_fields=['expected_revenue'])
    stamped = CrmLead.objects.values_list('write_date', flat=True).get(
        pk=lead.pk)
    aged = datetime(2000, 1, 1, tzinfo=dt_timezone.utc)
    CrmLead._base_manager.filter(pk=lead.pk).update(write_date=aged)
    _flush()
    after = CrmLead.objects.values_list('write_date', flat=True).get(
        pk=lead.pk)
    assert after == stamped != aged
