"""``Properties.type`` y ``PropertiesDefinition.type`` — los de la fuente.

≙ ``odoo19c: odoo/orm/fields_properties.py:52`` y ``:849``. Diseño en
``designs/properties-field-type.md`` del Workbench.

*Métrica:* el ``type`` que publica cada campo.
*Ciega a:* los caminos que el tipo activa; los mide la suite de cada uno.
"""
from orm.environments import Environment
from orm.fields import type_for
from orm.utils import SUPERUSER_ID


def _field(model, name):
    with Environment(None, SUPERUSER_ID, {}) as env:
        return env[model]._fields[name]


def test_a_properties_field_is_of_type_properties():
    assert _field('test_orm.message', 'attributes').type == 'properties'


def test_a_definition_field_is_of_type_properties_definition():
    assert _field('test_orm.discussion', 'attributes_definition').type == (
        'properties_definition')


def test_the_reflected_type_is_the_same():
    assert type_for(_field('test_orm.message', 'attributes')) == 'properties'
