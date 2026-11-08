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
from django.db import IntegrityError, transaction

from addons.base.models.ir_model import IrModel, IrModelConstraint
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
