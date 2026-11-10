"""Campos editables calculados por el mismo método — ``write`` no pierde el
recómputo pendiente de los hermanos no asignados.

≙ ``odoo19c: odoo/orm/models.py:4430-4437``: al escribir un campo de un
grupo ``field_computed`` se fuerza antes el cálculo de los campos del grupo
que no se asignan, porque dentro del alcance de protección ya no se
computarían. Modelo de la referencia: ``test_orm.shared.compute``
(``odoo/addons/test_orm/models/test_orm.py:2454-2476``); su prueba
``test_protection_shared_compute`` (``tests/test_onchange.py:1352``) pasa por
``Form``, y aquí se mide el mismo contrato por ``write``. Diseño en
``designs/write-announces-computed.md`` (TASK-API-0511).
"""
import pytest

pytestmark = pytest.mark.django_db


def _row(record):
    return type(record).objects.values('name', 'start', 'end').get(
        pk=record.id)


def test_defaults_come_from_the_shared_compute(env):
    record = env['test_orm.shared.compute'].create({})
    record.flush_model()
    # ``start`` es 0, falso: ``_compute_name`` no asigna ``name``.
    assert _row(record) == {'name': None, 'start': 0, 'end': 10}


def test_writing_one_sibling_keeps_the_pending_recompute_of_the_other(env):
    """``name`` deja ``start`` y ``end`` pendientes; escribir ``start``
    antes del volcado calcula ``end`` desde ``name`` y conserva el valor
    escrito de ``start``."""
    record = env['test_orm.shared.compute'].create({})
    record.flush_model()
    record.write({'name': '5->25'})
    record.write({'start': 7})
    record.flush_model()
    row = _row(record)
    assert row['start'] == 7
    assert row['end'] == 25
