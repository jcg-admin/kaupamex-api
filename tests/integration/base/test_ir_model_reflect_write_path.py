"""Tests — el CAMINO por el que los tres reflejos escriben su fila.

Contrato adaptado de ``odoo19c: odoo/addons/base/models/ir_model.py``:
``_reflect_inherits`` (``:1433-1504``), ``_reflect_constraint``
(``:1930-1976``) y ``_reflect_relation`` (``:2051-2069``).

Qué fija este archivo, y por qué es un eje aparte
=================================================

Los tres escriben **por debajo del ORM** en la fuente: ``upsert_en`` el
primero, ``execute_query(SQL(...))`` los otros dos. Ninguno pasa por ``create``
ni por ``write``, así que ninguno dispara el cómputo previo, las restricciones
declaradas ni las automatizaciones que la fuente cuelga del camino
interactivo.

Aquí el equivalente exacto son ``bulk_create`` y ``QuerySet.update()``, que son
los dos escritores de Django que **no** llaman a :meth:`save`. Es la misma
elección que ya documentan sus tres hermanos del mismo archivo
—``_reflect_models``, ``_reflect_fields`` y ``_update_selection``—; estos tres
eran los que faltaban.

Qué haría fallar a cada control
--------------------------------

``test_*_does_not_fire_the_save_hook``
    El eje. Lo hace fallar escribir con ``create``/``save``/``get_or_create``,
    que es como estaban los tres antes de #345: cada fila reflejada disparaba
    ``pre_save`` y ``post_save``, y con ellos el pase de precompute del ORM
    (``orm/models.py``) y los tres receptores sin ``sender`` de
    ``base_automation`` —uno de los cuales hace un ``SELECT`` por fila.

``test_an_ordinary_save_does_fire_the_hook``
    CONTROL POSITIVO del instrumento. Sin él, un receptor mal conectado daría
    cero llamadas siempre y los casos de arriba pasarían midiendo nada — el
    verde que no discrimina de ``metrica-decide-la-conclusion.md``.

``test_updating_a_changed_row_refreshes_updated_at``
    ``QuerySet.update()`` **no** dispara ``auto_now``. La fuente sí fija
    ``write_date=now()`` en su ``UPDATE`` crudo (``:1968``), así que omitirlo
    dejaría la marca de tiempo congelada — divergencia silenciosa.
"""
import pytest
from django.db.models.signals import post_save

from addons.base.models.ir_model import (
    IrModel, IrModelConstraint, IrModelInherit, IrModelRelation)
from addons.base.models.ir_module import IrModule
from addons.base.models.res_device import ResDeviceLog

pytestmark = pytest.mark.integration


class SaveHookProbe:
    """Cuenta cuántas veces el modelo dado pasa por ``post_save``."""

    def __init__(self, model):
        self.model = model
        self.calls = 0

    def __enter__(self):
        post_save.connect(self._count, sender=self.model, weak=False)
        return self

    def __exit__(self, *_exception):
        post_save.disconnect(self._count, sender=self.model)
        return False

    def _count(self, **_kwargs):
        self.calls += 1


def _module(name):
    row, _ = IrModule.objects.get_or_create(
        name=name, defaults={'shortdesc': name, 'state': 'installed'})
    return row


def _anchor_model():
    row, _ = IrModel.objects.get_or_create(
        model=ResDeviceLog._meta.label,
        defaults={'name': 'Registro de dispositivo'})
    return row


class TestTheProbeCanSeeThePhenomenon:
    """CONTROL POSITIVO — sin esto, un cero no significa nada."""

    def test_an_ordinary_save_does_fire_the_hook(self, db):
        module = _module('prueba_camino_control')
        model_row = _anchor_model()
        with SaveHookProbe(IrModelRelation) as probe:
            IrModelRelation(name='tabla_control', module=module,
                            model=model_row).save()
        assert probe.calls == 1


class TestReflectRelationWritesBelowTheOrm:

    def test_it_does_not_fire_the_save_hook(self, db):
        _module('prueba_camino_rel')
        _anchor_model()
        with SaveHookProbe(IrModelRelation) as probe:
            row = IrModelRelation._reflect_relation(
                ResDeviceLog, 'tabla_camino_rel', 'prueba_camino_rel')
        assert probe.calls == 0
        assert row.pk is not None

    def test_reflecting_twice_still_leaves_one_row(self, db):
        _module('prueba_camino_rel2')
        _anchor_model()
        first = IrModelRelation._reflect_relation(
            ResDeviceLog, 'tabla_camino_rel2', 'prueba_camino_rel2')
        second = IrModelRelation._reflect_relation(
            ResDeviceLog, 'tabla_camino_rel2', 'prueba_camino_rel2')
        assert first.pk == second.pk
        assert IrModelRelation.objects.filter(
            name='tabla_camino_rel2').count() == 1


class TestReflectConstraintWritesBelowTheOrm:

    def test_creating_does_not_fire_the_save_hook(self, db):
        _module('prueba_camino_con')
        _anchor_model()
        with SaveHookProbe(IrModelConstraint) as probe:
            row = IrModelConstraint._reflect_constraint(
                ResDeviceLog, 'con_camino_a', 'u', 'unique(name)',
                'prueba_camino_con', message='dup')
        assert probe.calls == 0
        assert row.pk is not None
        assert row.definition == 'unique(name)'

    def test_updating_does_not_fire_the_save_hook(self, db):
        _module('prueba_camino_con2')
        _anchor_model()
        IrModelConstraint._reflect_constraint(
            ResDeviceLog, 'con_camino_b', 'u', 'unique(name)',
            'prueba_camino_con2')
        with SaveHookProbe(IrModelConstraint) as probe:
            row = IrModelConstraint._reflect_constraint(
                ResDeviceLog, 'con_camino_b', 'u', 'unique(other)',
                'prueba_camino_con2')
        assert probe.calls == 0
        assert row is not None
        assert row.definition == 'unique(other)'
        stored = IrModelConstraint.objects.get(pk=row.pk)
        assert stored.definition == 'unique(other)'

    def test_an_unchanged_row_is_not_touched(self, db):
        _module('prueba_camino_con3')
        _anchor_model()
        IrModelConstraint._reflect_constraint(
            ResDeviceLog, 'con_camino_c', 'u', 'unique(name)',
            'prueba_camino_con3')
        again = IrModelConstraint._reflect_constraint(
            ResDeviceLog, 'con_camino_c', 'u', 'unique(name)',
            'prueba_camino_con3')
        assert again is None

    def test_updating_a_changed_row_refreshes_updated_at(self, db):
        _module('prueba_camino_con4')
        _anchor_model()
        created = IrModelConstraint._reflect_constraint(
            ResDeviceLog, 'con_camino_d', 'u', 'unique(name)',
            'prueba_camino_con4')
        before = IrModelConstraint.objects.get(pk=created.pk).updated_at
        IrModelConstraint._reflect_constraint(
            ResDeviceLog, 'con_camino_d', 'u', 'unique(other)',
            'prueba_camino_con4')
        after = IrModelConstraint.objects.get(pk=created.pk).updated_at
        assert after > before


class TestReflectInheritsWritesBelowTheOrm:

    @staticmethod
    def _seed_a_parent():
        """Siembra la fila de un ancestro del MRO del modelo ancla."""
        for base in ResDeviceLog.__mro__[1:]:
            meta = getattr(base, '_meta', None)
            if meta is None:
                continue
            label = f'{meta.app_label}.{meta.object_name}'
            if label == ResDeviceLog._meta.label:
                continue
            row, _ = IrModel.objects.get_or_create(
                model=label, defaults={'name': meta.object_name})
            return row
        raise AssertionError('el modelo ancla no tiene ancestro con _meta')

    def test_it_does_not_fire_the_save_hook(self, db):
        model_row = _anchor_model()
        self._seed_a_parent()
        with SaveHookProbe(IrModelInherit) as probe:
            registered = IrModelInherit._reflect_inherits(model_row)
        assert probe.calls == 0
        assert registered >= 1

    def test_reflecting_twice_registers_no_new_edge(self, db):
        model_row = _anchor_model()
        self._seed_a_parent()
        IrModelInherit._reflect_inherits(model_row)
        again = IrModelInherit._reflect_inherits(model_row)
        assert again == 0
