"""La mitad ``ir.model.fields`` de ``base_sparse_field`` (tarea #314).

Ejercita los cuatro símbolos portados de ``odoo19c:
addons/base_sparse_field/models/models.py`` — el vocabulario ``serialized``,
el campo ``serialization_field_id``, la guarda de escritura y la pasada de
reflexión — más el modelo de prueba ``SparseFieldsTest``.

Los que llevan ``django_db`` escriben en ``ir_model_fields``, que es una tabla
real; los demás son de registro y no la tocan.
"""
import pytest
from exceptions import UserError

from addons.base.models.ir_model import STATE_BASE, IrModel, IrModelFields
from addons.base_sparse_field.models.fields import Serialized, Sparse
from addons.base_sparse_field.models.ir_model_fields import (
    SERIALIZED_TTYPE,
    _ttype_of_sparse,
    apply_base_sparse_field_extensions,
    reflect_sparse_fields,
    sparse_descriptors_of,
)
from addons.base_sparse_field.models.sparse_fields_test import SparseFieldsTest

MODEL_LABEL = 'base_sparse_field.SparseFieldsTest'


# --- vocabulario y campo (≙ selection_add + serialization_field_id) ---------


def test_serialized_joins_the_ttype_vocabulary():
    """≙ ``ttype = fields.Selection(selection_add=[('serialized', …)])``."""
    ttype = IrModelFields._meta.get_field('ttype')
    assert (SERIALIZED_TTYPE, SERIALIZED_TTYPE) in ttype.choices


def test_the_serialization_field_points_at_serialized_rows_only():
    """El ``domain`` de la referencia, en la mitad que ``limit_choices_to`` cubre."""
    campo = IrModelFields._meta.get_field('serialization_field_id')
    assert campo.remote_field.model is IrModelFields
    # ``get_limit_choices_to()`` y no el atributo: en Django 6 el valor vive en
    # ``_limit_choices_to`` y el público es el accesor.
    assert campo.get_limit_choices_to() == {'ttype': SERIALIZED_TTYPE}
    assert campo.null is True


def test_applying_the_extensions_twice_is_a_no_op():
    """``ready()`` puede correr dos veces (autoreloader) y no debe duplicar."""
    antes = len(IrModelFields._meta.get_field('ttype').choices)
    apply_base_sparse_field_extensions()
    assert len(IrModelFields._meta.get_field('ttype').choices) == antes


# --- ttype_for (≙ que Serialized.type sea 'serialized') --------------------


def test_a_serialized_field_reflects_as_serialized():
    """Sin este encadenado saldría ``json``: ``Serialized`` es un ``JSONField``."""
    assert IrModelFields.ttype_for(Serialized()) == SERIALIZED_TTYPE


def test_every_other_field_still_reaches_the_base_map():
    """El relevo por ``None`` deja pasar lo que no reclama."""
    assert IrModelFields.ttype_for(IrModelFields._meta.get_field('name')) == 'char'
    assert IrModelFields.ttype_for(
        IrModelFields._meta.get_field('required')) == 'boolean'
    assert IrModelFields.ttype_for(
        IrModelFields._meta.get_field('model_id')) == 'many2one'


# --- descubrimiento de descriptores ----------------------------------------


def test_the_six_sparse_fields_of_the_test_model_are_found():
    """≙ los seis ``sparse='data'`` de ``Sparse_FieldsTest``."""
    assert sorted(sparse_descriptors_of(SparseFieldsTest)) == [
        'boolean', 'char', 'float', 'integer', 'partner', 'selection']


def test_a_sparse_field_declares_the_type_it_can():
    """``relational_model`` y ``coerce`` es todo lo que el descriptor sabe."""
    assert _ttype_of_sparse(Sparse('data', relational_model='base.ResPartner')) \
        == 'many2one'
    assert _ttype_of_sparse(Sparse('data', coerce=int)) == 'integer'
    assert _ttype_of_sparse(Sparse('data', coerce=float)) == 'float'
    # Sin conversor cae al mismo respaldo que ``ttype_for`` en ``base``.
    assert _ttype_of_sparse(Sparse('data')) == 'char'


# --- guarda de escritura (≙ write) -----------------------------------------


@pytest.fixture
def serialized_row(db):
    """La fila del campo serializado sobre la que cuelgan los dispersos."""
    modelo = IrModel.objects.create(
        model=MODEL_LABEL, name='Prueba de campos dispersos', state=STATE_BASE)
    return IrModelFields.objects.create(
        model=MODEL_LABEL, model_id=modelo, name='data',
        ttype=SERIALIZED_TTYPE, state=STATE_BASE)


@pytest.mark.django_db
def test_changing_the_storing_system_is_refused(serialized_row):
    """≙ *"Changing the storing system for field %s is not allowed"*."""
    fila = IrModelFields.objects.create(
        model=MODEL_LABEL, model_id=serialized_row.model_id, name='integer',
        ttype='integer', state=STATE_BASE, serialization_field_id=serialized_row)
    fila.serialization_field_id = None
    with pytest.raises(UserError, match='sistema de almacenamiento'):
        fila.save()


@pytest.mark.django_db
def test_renaming_a_sparse_field_is_refused(serialized_row):
    """≙ *"Renaming sparse field %s is not allowed"*."""
    fila = IrModelFields.objects.create(
        model=MODEL_LABEL, model_id=serialized_row.model_id, name='char',
        ttype='char', state=STATE_BASE, serialization_field_id=serialized_row)
    fila.name = 'renamed'
    with pytest.raises(UserError, match='renombrar'):
        fila.save()


@pytest.mark.django_db
def test_renaming_a_field_that_is_not_sparse_is_allowed(serialized_row):
    """La guarda es asimétrica a propósito: sólo protege a los dispersos."""
    fila = IrModelFields.objects.create(
        model=MODEL_LABEL, model_id=serialized_row.model_id, name='plain',
        ttype='char', state=STATE_BASE)
    fila.name = 'renamed'
    fila.save()
    fila.refresh_from_db()
    assert fila.name == 'renamed'


# --- reflexión (≙ _reflect_fields) -----------------------------------------


@pytest.mark.django_db
def test_reflection_creates_a_row_per_sparse_field_pointing_at_its_container():
    """La pasada que ``base`` no puede hacer: un ``Sparse`` no está en ``_meta``."""
    modelo = IrModel.objects.create(
        model=MODEL_LABEL, name='Prueba de campos dispersos', state=STATE_BASE)
    creados, actualizados = reflect_sparse_fields(IrModelFields, modelo)
    assert (creados, actualizados) == (6, 0)

    contenedor = IrModelFields.objects.get(model=MODEL_LABEL, name='data')
    assert contenedor.ttype == SERIALIZED_TTYPE
    dispersos = IrModelFields.objects.filter(
        model=MODEL_LABEL, serialization_field_id=contenedor)
    assert dispersos.count() == 6
    assert all(fila.store is False for fila in dispersos)
    assert dispersos.get(name='integer').ttype == 'integer'
    assert dispersos.get(name='partner').ttype == 'many2one'


@pytest.mark.django_db
def test_reflection_is_idempotent():
    """Corre en cada arranque; la segunda vez actualiza, no duplica."""
    modelo = IrModel.objects.create(
        model=MODEL_LABEL, name='Prueba de campos dispersos', state=STATE_BASE)
    reflect_sparse_fields(IrModelFields, modelo)
    creados, actualizados = reflect_sparse_fields(IrModelFields, modelo)
    assert (creados, actualizados) == (0, 6)
    assert IrModelFields.objects.filter(model=MODEL_LABEL).count() == 7


@pytest.mark.django_db
def test_a_model_without_sparse_fields_is_skipped():
    """Sin descriptores no se toca la base — la pasada corre en cada modelo."""
    modelo = IrModel.objects.create(
        model='base.IrModelFields', name='Campo', state=STATE_BASE)
    assert reflect_sparse_fields(IrModelFields, modelo) == (0, 0)
    assert not IrModelFields.objects.filter(model='base.IrModelFields').exists()


@pytest.mark.django_db
def test_a_sparse_field_naming_an_absent_container_raises():
    """≙ *"Serialization field %s not found for sparse field %s!"*."""

    class Huerfano(SparseFieldsTest):
        ausente = Sparse('inexistente')

        class Meta(SparseFieldsTest.Meta):
            proxy = True
            app_label = 'base_sparse_field'

    modelo = IrModel.objects.create(
        model='base_sparse_field.Huerfano', name='Huérfano', state=STATE_BASE)
    with pytest.raises(UserError, match='campo de serialización'):
        reflect_sparse_fields(IrModelFields, modelo)
