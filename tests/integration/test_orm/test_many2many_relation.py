"""``Many2many(comodel, relation, column1, column2)`` — H-API-1124.

≙ ``odoo19c: odoo/addons/test_orm/models/test_orm.py``:
``test_orm.category.discussions`` y ``test_orm.discussion.categories`` son los
dos extremos de UNA relación sobre ``test_orm_discussion_category``, con las
columnas ``category`` y ``discussion``. Antes de ``Many2manyField`` la fábrica
entregaba esos posicionales a Django como ``related_name``,
``related_query_name`` y ``limit_choices_to``, y la relación vivía en dos
tablas: un enlace desde un extremo no se veía desde el otro.
"""

import pytest
from django.apps import apps as django_apps
from django.db import connection

from addons.test_orm.models.test_orm import TestOrmCategory, TestOrmDiscussion
from orm.fields_relational import Many2many, Many2manyField

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def _columns(table):
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT column_name FROM information_schema.columns '
            'WHERE table_name = %s ORDER BY column_name', [table])
        return [row[0] for row in cursor.fetchall()]


def test_the_relation_is_one_table_with_the_source_columns():
    field = TestOrmCategory._meta.get_field('discussions')
    assert field.m2m_db_table() == 'test_orm_discussion_category'
    assert set(_columns('test_orm_discussion_category')) == {
        'id', 'category', 'discussion'}
    assert _columns('test_orm_testormcategory_discussions') == []
    assert _columns('test_orm_testormdiscussion_categories') == []


def test_a_link_from_one_end_is_seen_from_the_other(env):
    category = env['test_orm.category'].create({'name': 'Tag'})
    discussion = TestOrmDiscussion.objects.create(name='Thread')
    TestOrmCategory.objects.get(pk=category.id).discussions.add(discussion)
    assert list(discussion.categories.values_list('pk', flat=True)) == [
        category.id]


def test_the_positionals_no_longer_reach_django_as_other_parameters():
    field = TestOrmCategory._meta.get_field('discussions')
    assert not field.remote_field.limit_choices_to
    assert field.remote_field.related_name == 'categories'


def test_the_string_positional_is_the_label():
    field = Many2many('base.ResPartner', 'rel_x', 'a_id', 'b_id', 'Label')
    assert isinstance(field, Many2manyField)
    assert field.verbose_name == 'Label'
    assert (field.relation, field.column1, field.column2) == (
        'rel_x', 'a_id', 'b_id')


def test_a_positional_and_its_keyword_together_are_refused():
    with pytest.raises(TypeError):
        Many2many('base.ResPartner', 'rel_x', relation='rel_y')


def test_only_one_field_materializes_the_relation_table():
    """Sin el emparejamiento los dos extremos declaran la tabla y la
    migración la crearía dos veces."""
    owners = [
        f'{model._meta.label}.{field.name}'
        for model in django_apps.get_models()
        for field in model._meta.local_many_to_many
        if field.m2m_db_table() == 'test_orm_discussion_category']
    assert owners == ['test_orm.TestOrmCategory.discussions']
