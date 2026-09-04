"""Tests — las restricciones y las guardas de ``ir.model``.

Contrato adaptado de ``odoo19c: odoo/addons/base/models/ir_model.py:270-308``
(``_check_model_name``, ``_check_order``, ``_check_fold_name``), ``:346-351``
(``_unlink_if_manual``), ``:353-381`` (``unlink``), ``:415-422``
(``name_create``) y ``:483-497`` (``write``).

Lo que la fuente decide, y es lo que estos casos fijan
======================================================

Una fila de ``ir.model`` describe un modelo, y cuatro de sus campos no se
pueden mover sin que la descripcion deje de corresponder a nada: ``model``,
``state``, ``abstract`` y ``transient``. La fuente los cierra en ``write``.

El orden es texto que acaba interpolado en un ``ORDER BY``, asi que pasa por
dos filtros: la forma de la clausula (``_check_qorder``) y la existencia de
cada campo nombrado. Y borrar una fila arrastra lo que la apuntaba: campos
relacionados, crons e identificadores externos.

Que haria fallar a cada control
--------------------------------

``TestCheckOrder.test_an_order_that_is_not_a_clause_is_refused``
    El eje. Lo haria fallar no llamar a ``_check_qorder``: el texto entraria
    entero al ``ORDER BY``.

``TestCheckOrder.test_a_field_that_does_not_exist_is_refused``
    CONTROL de la segunda mitad: sin el, ``x_inexistente asc`` pasa la forma y
    revienta al consultar.

``TestCheckOrder.test_a_real_field_of_the_model_is_accepted``
    CONTROL POSITIVO. Sin el, un ``_check_order`` que rechazara todo pasaria
    los dos anteriores.

``TestWriteGuard.test_a_field_that_did_not_change_does_not_trip_the_guard``
    CONTROL POSITIVO de la guarda: sin el, una guarda que rechazara toda
    escritura pasaria el caso negativo.

``TestUnlink.test_a_base_model_row_cannot_be_deleted_by_hand``
    CONTROL de ``_unlink_if_manual``.
"""
import pytest

from addons.base.models.ir_model import IrModel, IrModelData
from django.core.exceptions import ValidationError
from exceptions import UserError

pytestmark = pytest.mark.integration


def _manual(model='x_prueba_ir_model', **extra):
    valores = {'name': 'Prueba', 'model': model, 'state': 'manual'}
    valores.update(extra)
    return IrModel.objects.create(**valores)


class TestCheckModelName:
    """≙ ``_check_model_name`` (``odoo19c: :270-275``)."""

    def test_a_manual_row_without_the_prefix_is_refused(self, db):
        row = IrModel(name='Prueba', model='sin_prefijo', state='manual')
        with pytest.raises(ValidationError, match='x_'):
            row._check_model_name()

    def test_an_alphabet_outside_the_allowed_one_is_refused(self, db):
        row = IrModel(name='Prueba', model='x_Con Mayusculas', state='manual')
        with pytest.raises(ValidationError, match='minúsculas'):
            row._check_model_name()

    def test_a_base_row_does_not_need_the_prefix(self, db):
        row = IrModel(name='Socio', model='res.partner', state='base')
        row._check_model_name()


class TestCheckOrder:
    """≙ ``_check_order`` (``odoo19c: :277-302``)."""

    def test_an_order_that_is_not_a_clause_is_refused(self, db):
        row = IrModel(name='Prueba', model='base.IrModel', state='base',
                      order='drop table ir_model')
        with pytest.raises(ValidationError, match='Orden inválido'):
            row._check_order()

    def test_a_field_that_does_not_exist_is_refused(self, db):
        row = IrModel(name='Prueba', model='base.IrModel', state='base',
                      order='x_inexistente asc')
        with pytest.raises(ValidationError, match='x_inexistente'):
            row._check_order()

    def test_a_real_field_of_the_model_is_accepted(self, db):
        row = IrModel(name='Prueba', model='base.IrModel', state='base',
                      order='model asc, id desc')
        row._check_order()

    def test_the_magic_columns_are_always_accepted(self, db):
        row = IrModel(name='Prueba', model='base.IrModel', state='base',
                      order='id desc')
        row._check_order()


class TestCheckFoldName:
    """≙ ``_check_fold_name`` (``odoo19c: :304-308``)."""

    def test_a_fold_field_that_is_not_a_field_is_refused(self, db):
        row = IrModel(name='Prueba', model='base.IrModel', state='base',
                      fold_name='x_no_existe')
        with pytest.raises(ValidationError, match='Campo de plegado'):
            row._check_fold_name()

    def test_a_real_field_is_accepted_as_fold_field(self, db):
        row = IrModel(name='Prueba', model='base.IrModel', state='base',
                      fold_name='abstract')
        row._check_fold_name()


class TestWriteGuard:
    """≙ la guarda de ``write`` (``odoo19c: :483-486``)."""

    @pytest.mark.parametrize('field_name, value', [
        ('model', 'x_otro_nombre'),
        ('state', 'base'),
        ('abstract', True),
        ('transient', True),
    ])
    def test_an_unmodifiable_field_is_refused(self, db, field_name, value):
        row = _manual()
        setattr(row, field_name, value)
        with pytest.raises(UserError, match=field_name):
            row.save()

    def test_a_field_that_did_not_change_does_not_trip_the_guard(self, db):
        row = _manual()
        row.name = 'Otra etiqueta'
        row.save()
        row.refresh_from_db()
        assert row.name == 'Otra etiqueta'


class TestNameCreate:
    """≙ ``name_create`` (``odoo19c: :415-422``)."""

    def test_it_infers_the_technical_name_from_the_label(self, db):
        pk, _label = IrModel.name_create('My New Model')
        assert IrModel.objects.get(pk=pk).model == 'x_my_new_model'


class TestUnlink:
    """≙ ``unlink`` y ``_unlink_if_manual`` (``odoo19c: :346-381``)."""

    def test_a_base_model_row_cannot_be_deleted_by_hand(self, db):
        row = _manual(model='x_de_modulo')
        IrModel.objects.filter(pk=row.pk).update(state='base')
        row.refresh_from_db()
        with pytest.raises(UserError, match='datos de módulo'):
            row.delete()

    def test_deleting_drags_the_external_ids_that_name_it(self, db):
        row = _manual(model='x_con_xmlid')
        IrModelData.objects.create(
            name='algo', module='prueba', model='x_con_xmlid', res_id=1)
        row.delete()
        assert not IrModelData.objects.filter(model='x_con_xmlid').exists()
