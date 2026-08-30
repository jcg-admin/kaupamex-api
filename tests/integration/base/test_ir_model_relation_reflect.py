"""Tests — el registro de tablas intermedias de Many2many (``ir.model.relation``).

Contrato adaptado de ``odoo19c: odoo/addons/base/models/ir_model.py:2051-2069``
(``_reflect_relation``) y ``:2022-2049`` (``_module_data_uninstall``).

Lo que la fuente decide, y es lo que estos casos fijan
======================================================

``_reflect_relation(model, table, module)`` deja **una** fila por
``(tabla, módulo)``: su ``INSERT`` va condicionado a un ``SELECT`` de
existencia, así que llamarlo dos veces no duplica. Sin ese registro,
``_module_data_uninstall`` no sabe qué tablas dejó un módulo — la trazabilidad
del Many2many empieza aquí.

``_module_data_uninstall`` sólo suelta una tabla cuando **todos** sus dueños
están dentro del lote que se desinstala. Su propio comentario lo dice: *"as
installed modules have defined this element we must not delete it!"*.

Qué haría fallar a cada control
--------------------------------

``TestReflectRelation.test_reflecting_twice_leaves_one_row``
    El eje de la idempotencia. Lo haría fallar un ``create`` pelado en vez del
    ``get_or_create`` que reproduce el ``SELECT``-antes-de-``INSERT``.

``TestReflectRelation.test_an_unknown_module_is_refused_by_name``
    CONTROL: la fuente resuelve el módulo con una subconsulta que da ``NULL``
    y su ``INSERT`` revienta por ``NOT NULL``. Sin esta guarda, aquí saldría un
    ``IntegrityError`` sin decir qué faltó.

``TestModuleDataUninstall.test_a_table_owned_by_another_module_survives``
    CONTROL de la guarda de propiedad. Lo haría fallar borrar por módulo sin
    mirar quién más declara el mismo nombre de tabla — que es el caso que la
    fuente comenta expresamente.
"""
import pytest

from addons.base.models.ir_model import IrModel, IrModelRelation
from addons.base.models.ir_module import IrModule
from addons.base.models.res_device import ResDeviceLog
from exceptions import AccessError
from orm.environments import sudo

pytestmark = pytest.mark.integration

TABLE = 'res_device_log_prueba_rel'


def _module(name):
    row, _ = IrModule.objects.get_or_create(
        name=name, defaults={'shortdesc': name, 'state': 'installed'})
    return row


def _reflected_model():
    """La fila de ``ir_model`` del modelo ancla.

    La siembra el test y no el arranque: ``_reflect_models`` corre al instalar
    un módulo, y la base de pruebas no pasa por ahí. Es la misma preparación
    que usa ``test_ir_model_access_check.py``.
    """
    row, _ = IrModel.objects.get_or_create(
        model=ResDeviceLog._meta.label,
        defaults={'name': 'Registro de dispositivo'})
    return row


class TestReflectRelation:
    """≙ ``_reflect_relation`` — el registro, no el DDL."""

    def test_it_records_the_table_with_its_model_and_module(self, db):
        _module('prueba_rel_a')
        _reflected_model()
        row = IrModelRelation._reflect_relation(
            ResDeviceLog, TABLE, 'prueba_rel_a')
        assert row.name == TABLE
        assert row.module.name == 'prueba_rel_a'
        assert row.model.model == ResDeviceLog._meta.label

    def test_reflecting_twice_leaves_one_row(self, db):
        _module('prueba_rel_b')
        _reflected_model()
        first = IrModelRelation._reflect_relation(
            ResDeviceLog, TABLE, 'prueba_rel_b')
        second = IrModelRelation._reflect_relation(
            ResDeviceLog, TABLE, 'prueba_rel_b')
        assert first.pk == second.pk
        assert IrModelRelation.objects.filter(name=TABLE).count() == 1

    def test_an_unknown_module_is_refused_by_name(self, db):
        with pytest.raises(ValueError, match='prueba_rel_inexistente'):
            IrModelRelation._reflect_relation(
                ResDeviceLog, TABLE, 'prueba_rel_inexistente')

    def test_an_unregistered_model_is_refused_by_name(self, db):
        _module('prueba_rel_c')
        IrModel.objects.filter(model=ResDeviceLog._meta.label).delete()
        with pytest.raises(ValueError, match=ResDeviceLog._meta.label):
            IrModelRelation._reflect_relation(
                ResDeviceLog, TABLE, 'prueba_rel_c')


class TestModuleDataUninstall:
    """≙ ``_module_data_uninstall`` — su mitad de datos."""

    def test_it_needs_administrator_access(self, db):
        with pytest.raises(AccessError):
            IrModelRelation._module_data_uninstall([])

    def test_a_table_of_the_batch_is_dropped_from_the_registry(self, db):
        module = _module('prueba_rel_d')
        _reflected_model()
        with sudo():
            IrModelRelation._reflect_relation(
                ResDeviceLog, TABLE, 'prueba_rel_d')
            dropped = IrModelRelation._module_data_uninstall([module])
        assert dropped == [TABLE]
        assert not IrModelRelation.objects.filter(name=TABLE).exists()

    def test_a_table_owned_by_another_module_survives(self, db):
        mine = _module('prueba_rel_e')
        other = _module('prueba_rel_f')
        _reflected_model()
        with sudo():
            IrModelRelation._reflect_relation(
                ResDeviceLog, TABLE, 'prueba_rel_e')
            IrModelRelation._reflect_relation(
                ResDeviceLog, TABLE, 'prueba_rel_f')
            dropped = IrModelRelation._module_data_uninstall([mine])
        assert dropped == []
        assert IrModelRelation.objects.filter(name=TABLE).count() == 2
        assert other.pk is not None
