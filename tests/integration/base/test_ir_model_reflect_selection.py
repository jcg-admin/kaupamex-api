"""Tests — el reflejo de selecciones y de objetos de tabla.

Contrato adaptado de ``odoo19c: odoo/addons/base/models/ir_model.py:1527-1663``
(``ir.model.fields.selection``) y ``:1929-2003`` (``ir.model.constraint``).

Lo que la fuente decide, y es lo que estos casos fijan
======================================================

``_update_selection`` sincroniza la lista de valores de un campo con lo que
hay en la tabla: el indice en la lista **es** la secuencia, una fila que ya
dice lo mismo no se toca, y quitar un valor avisa antes de borrarlo — porque
las filas que lo guardaban quedan apuntando a nada.

``_reflect_constraint`` devuelve la fila **solo si creo o modifico**; devuelve
``None`` cuando la fila ya decia lo mismo. Esa distincion es la que permite a
su llamador saber que cambio.

Que haria fallar a cada control
--------------------------------

``TestUpdateSelection.test_the_index_in_the_list_becomes_the_sequence``
    El eje del orden. Lo haria fallar guardar la secuencia de cualquier otra
    forma: el orden en que la interfaz ofrece los valores sale de ahi.

``TestUpdateSelection.test_a_value_missing_from_the_new_list_is_removed``
    CONTROL: sin el, una sincronizacion que solo insertara dejaria valores
    muertos y pasaria los demas casos.

``TestReflectConstraint.test_reflecting_an_unchanged_constraint_returns_none``
    CONTROL de la distincion cambio/no-cambio, que es lo unico que este metodo
    comunica a su llamador.

``TestReflectModel.test_it_reads_the_table_objects_from_meta``
    CONTROL POSITIVO del sitio: los objetos de tabla viven en ``Meta`` y no en
    un ``_table_objects``, y de ahi salen su nombre, su tipo y su definicion.
"""
import pytest

from addons.base.models.ir_model import (
    IrModel, IrModelConstraint, IrModelData, IrModelFields,
    IrModelFieldsSelection)
from addons.base.models.ir_module import IrModule
from exceptions import AccessError, UserError
from orm.environments import sudo

pytestmark = pytest.mark.integration

MODEL_LABEL = 'base.IrModelData'


def _module(name):
    row, _ = IrModule.objects.get_or_create(
        name=name, defaults={'shortdesc': name, 'state': 'installed'})
    return row


def _model_row(label=MODEL_LABEL):
    row, _ = IrModel.objects.get_or_create(
        model=label, defaults={'name': 'Dato de modelo'})
    return row


def _field_row(name='x_estado'):
    return IrModelFields.objects.create(
        model=MODEL_LABEL, name=name, field_description='Estado',
        ttype='selection', state='manual', model_id=_model_row())


class TestUpdateSelection:
    """≙ ``_update_selection`` (``odoo19c: :1602-1650``)."""

    def test_the_index_in_the_list_becomes_the_sequence(self, db):
        _field_row()
        rows = IrModelFieldsSelection._update_selection(
            MODEL_LABEL, 'x_estado', [('a', 'Alfa'), ('b', 'Beta')])
        assert rows['a']['sequence'] == 0
        assert rows['b']['sequence'] == 1

    def test_a_row_that_already_says_the_same_is_left_alone(self, db):
        _field_row()
        IrModelFieldsSelection._update_selection(
            MODEL_LABEL, 'x_estado', [('a', 'Alfa')])
        before = IrModelFieldsSelection.objects.get(value='a').pk
        IrModelFieldsSelection._update_selection(
            MODEL_LABEL, 'x_estado', [('a', 'Alfa')])
        assert IrModelFieldsSelection.objects.get(value='a').pk == before

    def test_a_value_missing_from_the_new_list_is_removed(self, db):
        _field_row()
        IrModelFieldsSelection._update_selection(
            MODEL_LABEL, 'x_estado', [('a', 'Alfa'), ('b', 'Beta')])
        rows = IrModelFieldsSelection._update_selection(
            MODEL_LABEL, 'x_estado', [('a', 'Alfa')])
        assert set(rows) == {'a'}
        assert not IrModelFieldsSelection.objects.filter(value='b').exists()

    def test_a_field_that_is_not_registered_is_refused_by_name(self, db):
        with pytest.raises(ValueError, match='no_registrado'):
            IrModelFieldsSelection._update_selection(
                MODEL_LABEL, 'no_registrado', [('a', 'Alfa')])


class TestGetSelection:
    """≙ ``_get_selection`` y ``_get_selection_data`` (``odoo19c: :1527-1541``)."""

    def test_it_returns_the_pairs_in_sequence_order(self, db):
        field = _field_row()
        IrModelFieldsSelection.objects.create(
            field_id=field, value='b', name='Beta', sequence=20)
        IrModelFieldsSelection.objects.create(
            field_id=field, value='a', name='Alfa', sequence=10)
        assert IrModelFieldsSelection._get_selection(field.pk) == [
            ('a', 'Alfa'), ('b', 'Beta')]


class TestUnlinkGuard:
    """≙ ``_unlink_if_manual`` (``odoo19c: :1723-1731``)."""

    def test_a_value_of_a_base_field_is_not_deleted_by_hand(self, db):
        field = _field_row()
        row = IrModelFieldsSelection.objects.create(
            field_id=field, value='a', name='Alfa')
        # El campo pasa a base DESPUES de crear el valor: la guarda de
        # :meth:`save` cierra el alta, y este caso mide la de :meth:`delete`.
        IrModelFields.objects.filter(pk=field.pk).update(state='base')
        row.refresh_from_db()
        with pytest.raises(UserError, match='campo base'):
            row.delete()


class TestReflectConstraint:
    """≙ ``_reflect_constraint`` (``odoo19c: :1929-1985``)."""

    def test_it_records_the_constraint_with_its_definition(self, db):
        _module('prueba_cons_a')
        _model_row()
        row = IrModelConstraint._reflect_constraint(
            IrModelData, 'x_prueba_uniq', 'u', 'UNIQUE (name)',
            'prueba_cons_a')
        assert row.name == 'x_prueba_uniq'
        assert row.definition == 'UNIQUE (name)'
        assert row.type == 'u'

    def test_reflecting_an_unchanged_constraint_returns_none(self, db):
        _module('prueba_cons_b')
        _model_row()
        IrModelConstraint._reflect_constraint(
            IrModelData, 'x_prueba_uniq', 'u', 'UNIQUE (name)',
            'prueba_cons_b')
        again = IrModelConstraint._reflect_constraint(
            IrModelData, 'x_prueba_uniq', 'u', 'UNIQUE (name)',
            'prueba_cons_b')
        assert again is None

    def test_a_changed_definition_returns_the_row(self, db):
        _module('prueba_cons_c')
        _model_row()
        IrModelConstraint._reflect_constraint(
            IrModelData, 'x_prueba_uniq', 'u', 'UNIQUE (name)',
            'prueba_cons_c')
        changed = IrModelConstraint._reflect_constraint(
            IrModelData, 'x_prueba_uniq', 'u', 'UNIQUE (name, module)',
            'prueba_cons_c')
        assert changed is not None
        assert changed.definition == 'UNIQUE (name, module)'

    def test_without_a_module_nothing_is_recorded(self, db):
        _model_row()
        assert IrModelConstraint._reflect_constraint(
            IrModelData, 'x_prueba_uniq', 'u', 'UNIQUE (name)', '') is None
        assert not IrModelConstraint.objects.filter(
            name='x_prueba_uniq').exists()


class TestReflectModel:
    """≙ ``_reflect_model`` (``odoo19c: :1992-2003``)."""

    def test_it_reads_the_table_objects_from_meta(self, db):
        _module('base')
        _model_row()
        rows = IrModelConstraint._reflect_model(IrModelData)
        by_name = {row.name: row for row in rows}
        assert 'ir_model_data_module_name_uniq' in by_name
        assert by_name['ir_model_data_module_name_uniq'].type == 'u'
        assert 'UNIQUE' in by_name['ir_model_data_module_name_uniq'].definition
        assert by_name['ir_model_data_model_res'].type == 'i'


class TestModuleDataUninstall:
    """≙ la mitad de datos de ``unlink`` (``odoo19c: :1873-1923``)."""

    def test_it_needs_administrator_access(self, db):
        with pytest.raises(AccessError):
            IrModelConstraint._module_data_uninstall([])

    def test_a_constraint_owned_by_another_module_survives(self, db):
        mine = _module('prueba_cons_d')
        _module('prueba_cons_e')
        _model_row()
        with sudo():
            IrModelConstraint._reflect_constraint(
                IrModelData, 'x_compartida', 'u', 'UNIQUE (name)',
                'prueba_cons_d')
            IrModelConstraint._reflect_constraint(
                IrModelData, 'x_compartida', 'u', 'UNIQUE (name)',
                'prueba_cons_e')
            dropped = IrModelConstraint._module_data_uninstall([mine])
        assert dropped == []
        assert IrModelConstraint.objects.filter(name='x_compartida').count() == 2
