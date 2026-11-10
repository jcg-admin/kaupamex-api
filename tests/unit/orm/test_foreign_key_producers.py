"""Los productores de las claves foráneas esperadas del registro.

≙ ``Many2one.update_db_foreign_key`` y ``Many2many.update_db_foreign_keys``
(``odoo19c: odoo/orm/fields_relational.py:306-320, 1356-1367``): no escriben
en la base; declaran en ``Registry._foreign_keys`` lo que
``check_foreign_keys`` comprobará al final de ``init_models``.
Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
foreign-keys-update-db.md``.
"""
import pytest
from django.db import connection

from orm.registry import Registry

pytestmark = pytest.mark.django_db


@pytest.fixture
def registry(db):
    registry = Registry(connection.alias)
    registry._foreign_keys = {}
    yield registry
    del registry._foreign_keys


def _field(registry, model_name, name):
    model = registry.models[model_name]
    return model, model._meta.get_field(name)


def test_many2one_declares_its_expected_foreign_key(registry):
    model, field = _field(registry, 'test_orm.category', 'parent')
    field.update_db_foreign_key(model, field.column)
    table, column, ondelete, owner, _module = registry._foreign_keys[
        ('test_orm_category', 'parent')]
    assert (table, column, ondelete) == ('test_orm_category', 'id', 'cascade')
    assert owner is model


def test_many2one_without_ondelete_declares_set_null(registry):
    """``self.ondelete or 'set null'`` (``:319``)."""
    model, field = _field(registry, 'test_orm.discussion', 'moderator')
    field.ondelete = None
    try:
        field.update_db_foreign_key(model, field.column)
    finally:
        del field.ondelete
    assert registry._foreign_keys[
        ('test_orm_discussion', 'moderator')][2] == 'set null'


def test_many2one_declares_nothing_towards_an_unmanaged_comodel(registry):
    """Sin tabla ordinaria en el comodelo no hay FK (``:311-316``)."""
    model, field = _field(registry, 'test_orm.category', 'parent')
    field.related_model._meta.managed = False
    try:
        field.update_db_foreign_key(model, field.column)
    finally:
        field.related_model._meta.managed = True
    assert registry._foreign_keys == {}


def test_many2many_declares_both_columns(registry):
    model, field = _field(registry, 'test_orm.category', 'discussions')
    field.update_db_foreign_keys(model)
    fks = registry._foreign_keys
    assert fks[('test_orm_discussion_category', 'category')][:3] == (
        'test_orm_category', 'id', 'cascade')
    assert fks[('test_orm_discussion_category', 'discussion')][:2] == (
        'test_orm_discussion', 'id')


def test_many2many_column1_does_not_override_a_previous_declaration(
        registry):
    """``force=False`` en ``column1`` (``:1361``): gana quien declaró antes."""
    model, field = _field(registry, 'test_orm.category', 'discussions')
    key = ('test_orm_discussion_category', 'category')
    registry._foreign_keys[key] = ('test_orm_category', 'id', 'restrict',
                                   model, 'previous')
    field.update_db_foreign_keys(model)
    assert registry._foreign_keys[key][2] == 'restrict'
