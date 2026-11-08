"""El mensaje de usuario de un error de base de datos, contra la referencia.

≙ ``_sql_error_to_message`` y ``_sql_error_to_message_generic``
(``odoo19c: odoo/orm/models.py:3269-3339``). El primero busca el mensaje de
la restricción violada —primero la fila de ``ir.model.constraint`` de ese
modelo, después el objeto de tabla— y si no hay ninguno cae en el segundo,
que compone el texto por la clase del error.

En este árbol el error llega como el ``DatabaseError`` de Django, y el
diagnóstico de PostgreSQL vive en su ``__cause__``: un método que lea
``exc.diag`` no ve nunca el nombre de la restricción. Los objetos de tabla
tienen su hogar en ``Meta.constraints`` (``atributos-de-clase-de-modelo.md``),
y su mensaje es el ``violation_error_message`` que declaran.
"""
import pytest
from django.db import IntegrityError, connection, transaction

from addons.base.models.ir_model import (IrModel, IrModelAccess,
                                         IrModelConstraint)
from addons.base.models.ir_module import IrModule
from addons.base.models.res_groups import ResGroups, ResGroupsPrivilege
from orm.environments import env as current_environment

pytestmark = pytest.mark.django_db


def _violation(action):
    with pytest.raises(IntegrityError) as caught, transaction.atomic():
        action()
    return caught.value


def _duplicate_name():
    privilege = ResGroupsPrivilege.objects.create(name='Privilegio sql')
    ResGroups.objects.create(name='Repetido sql', privilege=privilege)
    return _violation(lambda: ResGroups.objects.create(
        name='Repetido sql', privilege=privilege))


def test_the_declared_message_of_the_table_object_is_used():
    exc = _duplicate_name()
    assert ResGroups._sql_error_to_message(exc) == (
        'El nombre del grupo tiene que ser único dentro de su privilegio.')


def test_the_message_of_the_constraint_row_of_the_model_wins():
    exc = _duplicate_name()
    model = IrModel._get('res.groups') or IrModel.objects.create(
        model='res.groups', name='Access Groups')
    module, _ = IrModule.objects.get_or_create(name='base')
    IrModelConstraint.objects.create(
        name='res_groups_name_uniq', model=model, module=module, type='u',
        message='Mensaje registrado')
    assert ResGroups._sql_error_to_message(exc) == 'Mensaje registrado'


def test_a_missing_value_gets_the_generic_message():
    exc = _violation(lambda: ResGroups.objects.create(name=None))
    model = IrModel._get('res.groups')
    model_string = (model and model.name) or ResGroups._description
    field_string = ResGroups._meta.get_field('name')._description_string(
        current_environment())
    assert ResGroups._sql_error_to_message(exc) == (
        f"Missing required value for the field '{field_string}' (name).\n"
        f"Model: '{model_string}' (res.groups)\n"
        "- create/update: a mandatory field is not set\n"
        "- delete: another model requires the record being deleted, you can "
        "archive it instead\n")


def test_a_check_with_a_declared_message_uses_it():
    """``res_groups_check_api_key_duration`` declara su mensaje: es la rama
    del objeto de tabla, también para un ``CHECK``."""
    exc = _violation(lambda: ResGroups.objects.create(
        name='Negativa sql', api_key_duration=-1))
    assert ResGroups._sql_error_to_message(exc) == (
        'La duración de la API key no puede ser negativa.')


def test_a_referenced_row_gets_the_foreign_key_message():
    """Borrar un grupo que un permiso referencia viola la clave foránea de
    ``ir_model_access``: la tabla del diagnóstico no es la de
    ``res.groups``, así que el modelo es ``Unknown``, y sin una sola columna
    el campo se nombra por la restricción (``odoo19c: models.py:
    3320-3328``). Las claves foráneas de Django son diferibles; se fuerzan
    inmediatas para que la violación ocurra dentro de la prueba."""
    group = ResGroups.objects.create(name='Referenciado sql')
    model = IrModel._get('res.groups') or IrModel.objects.create(
        model='res.groups', name='Access Groups')
    IrModelAccess.objects.create(
        name='acl sql', model_id=model, group_id=group, perm_read=True)

    def delete():
        with connection.cursor() as cursor:
            cursor.execute('SET CONSTRAINTS ALL IMMEDIATE')
            cursor.execute('DELETE FROM res_groups WHERE id = %s', [group.pk])

    exc = _violation(delete)
    constraint = exc.__cause__.diag.constraint_name
    assert ResGroups._sql_error_to_message(exc) == (
        "Another model is using the record you are trying to delete.\n\n"
        "The troublemaker is: Unknown\n"
        f"Thanks to the following constraint: {constraint}\n"
        "How about archiving the record instead?")
