"""``BaseModel.new`` — ≙ ``odoo19c: odoo/orm/models.py:6441-6460``.

El contrato es el del docstring de la fuente: el registro vive en el caché del
entorno y no en la base; ``origin`` es el registro real detrás de él y se lee
con ``_origin``; dos registros nuevos con el mismo origen son iguales; ``ref``
lo identifica entre otros nuevos y viaja dentro de su ``id``.
"""

import pytest

from orm.identifiers import NewId

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def test_new_record_lives_in_the_cache_not_in_the_table(env):
    Line = env['test_orm.multi.line']
    before = Line.search_count([])
    line = Line.new({'name': 'uno'})
    assert isinstance(line.id, NewId)
    assert not line.id
    assert line.name == 'uno'
    assert Line.search_count([]) == before


def test_values_are_shared_by_every_recordset_of_the_same_new_id(env):
    Line = env['test_orm.multi.line']
    line = Line.new({'name': 'uno'})
    assert Line.browse(line._ids).name == 'uno'


def test_an_unset_field_reads_its_empty_value(env):
    line = env['test_orm.multi.line'].new({})
    assert line.name is False


def test_a_many2one_value_is_converted_to_a_record(env):
    multi = env['test_orm.multi'].create({})
    line = env['test_orm.multi.line'].new({'name': 'uno', 'multi': multi.id})
    assert line.multi == multi


def test_origin_is_the_real_record_behind_the_new_one(env):
    multi = env['test_orm.multi'].create({})
    new = env['test_orm.multi'].new({}, origin=multi)
    assert new._origin == multi
    assert new.id.origin == multi.id


def test_two_new_records_with_the_same_origin_are_equal(env):
    multi = env['test_orm.multi'].create({})
    Multi = env['test_orm.multi']
    assert Multi.new(origin=multi) == Multi.new(origin=multi)
    assert Multi.new() != Multi.new()


def test_ref_is_carried_by_the_id(env):
    line = env['test_orm.multi.line'].new({}, ref='virtual_1')
    assert line.id.ref == 'virtual_1'


def test_an_unknown_field_is_rejected(env):
    with pytest.raises(ValueError, match='Invalid field'):
        env['test_orm.multi.line'].new({'no_such_field': 1})


def test_a_many2one_dict_value_becomes_a_new_record(env):
    """≙ ``Many2one.convert_to_cache``, rama ``dict`` (``odoo19c: odoo/orm/
    fields_relational.py:339-343``): el ``dict`` es un registro nuevo del
    comodelo, con su ``id`` como origen."""
    multi = env['test_orm.multi'].create({})
    Line = env['test_orm.multi.line']
    line = Line.new({})
    value = Line._fields['multi'].convert_to_cache({'id': multi.id}, line)
    assert isinstance(value, NewId)
    assert value.origin == multi.id
    assert env['test_orm.multi'].browse((value,))._origin == multi
