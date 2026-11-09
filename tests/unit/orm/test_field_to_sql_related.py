"""``_field_to_sql`` recorre un ``related`` no almacenado.

≙ ``odoo19c: odoo/orm/models.py`` (``_field_to_sql``): un ``related`` sin
columna se resuelve con ``_traverse_related_sql`` y sus JOIN. Diseño en
``designs/field-to-sql-nonstored-related.md`` del Workbench.

*Métrica:* el ``SQL.code`` de la columna y las uniones de ``Query``.
*Ciega a:* la lectura de valores, que hace el descriptor del campo.
"""
import pytest
from django.contrib.auth import get_user_model

from orm.environments import env as current_env
from orm.environments import sudo, user_scope
from tools.query import Query

pytestmark = pytest.mark.django_db


@pytest.fixture
def environment():
    user = get_user_model().objects.create_user(
        login='field-to-sql-related', password=None, name='u')
    with user_scope(user.pk), sudo():
        yield current_env()


def _model(environment, name):
    return environment[name].browse(())


def _query(model):
    return Query(model.env, model._table, model._table_sql)


def _joins(query):
    return ' '.join(query.from_clause.code.split())


def test_a_one_hop_related_reads_the_joined_column(environment):
    related = _model(environment, 'test_orm.related')
    query = _query(related)
    sql = related._field_to_sql(related._table, 'foo_name', query)
    assert sql.code == '"test_orm_related__foo_id"."name"'
    assert 'JOIN "test_orm_related_foo" AS "test_orm_related__foo_id"' \
        in _joins(query)


def test_a_two_hop_related_reads_the_second_joined_column(environment):
    related = _model(environment, 'test_orm.related')
    query = _query(related)
    sql = related._field_to_sql(related._table, 'foo_bar_name', query)
    assert sql.code == '"test_orm_related__foo_id__bar_id"."name"'


def test_a_related_field_can_be_ordered(environment):
    related = _model(environment, 'test_orm.related')
    query = _query(related)
    sql = related._order_to_sql('foo_name desc', query)
    assert ' '.join(sql.code.split()) == \
        '"test_orm_related__foo_id"."name" DESC'


def test_a_computed_field_without_related_is_still_rejected(environment):
    category = _model(environment, 'test_orm.category')
    with pytest.raises(ValueError):
        category._field_to_sql(category._table, 'depth', _query(category))
