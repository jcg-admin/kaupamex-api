"""``BaseModel._order_to_sql`` y ``_order_field_to_sql``.

≙ ``odoo19c: odoo/orm/models.py:5224-5322``. Diseño en
``designs/order-to-sql.md`` del Workbench. Portadores: ``test_orm.city`` y
``test_orm.country`` (los de ``test_sort``), ``test_orm.category`` y
``test_orm.message``.

*Métrica:* el ``SQL.code`` del orden (espacios normalizados), las uniones de
``Query`` y ``Query._order_groupby``.
*Ciega a:* la ejecución del ``SELECT``; ``_search`` sigue ordenando con
``order_to_django``.
"""
import pytest
from django.contrib.auth import get_user_model

from exceptions import UserError
from orm.environments import env as current_env
from orm.environments import sudo, user_scope
from tools.query import Query

pytestmark = pytest.mark.django_db


@pytest.fixture
def environment():
    user = get_user_model().objects.create_user(
        login='order-to-sql', password=None, name='u')
    with user_scope(user.pk), sudo():
        yield current_env()


def _model(environment, name):
    return environment[name].browse(())


def _query(model):
    return Query(model.env, model._table, model._table_sql)


def _order(model, order, **kwargs):
    query = _query(model)
    sql = model._order_to_sql(order, query, **kwargs)
    return ' '.join(sql.code.split()), query


def test_a_plain_term_keeps_direction_and_nulls(environment):
    city = _model(environment, 'test_orm.city')
    code, query = _order(city, 'name desc nulls last')
    assert code == '"test_orm_city"."name" DESC NULLS LAST'
    assert [term.code for term in query._order_groupby] == [
        '"test_orm_city"."name"']


def test_reverse_flips_direction_and_nulls(environment):
    city = _model(environment, 'test_orm.city')
    code, _query_ = _order(city, 'name asc nulls first, id', reverse=True)
    assert code == ('"test_orm_city"."name" DESC NULLS LAST,'
                    ' "test_orm_city"."id" DESC')


def test_an_empty_order_uses_the_model_order(environment):
    country = _model(environment, 'test_orm.country')
    code, _query_ = _order(country, None)
    assert code == '"test_orm_country"."name" , "test_orm_country"."id"'


def test_a_boolean_orders_with_coalesce(environment):
    message = _model(environment, 'test_orm.message')
    code, _query_ = _order(message, 'important desc')
    assert code == 'COALESCE("test_orm_message"."important", FALSE) DESC'


def test_a_many2one_delegates_to_the_comodel_order_through_a_join(environment):
    city = _model(environment, 'test_orm.city')
    code, query = _order(city, 'country_id desc')
    assert code == ('"test_orm_city__country_id"."name" DESC ,'
                    ' "test_orm_city__country_id"."id" DESC')
    assert 'LEFT JOIN "test_orm_country" AS "test_orm_city__country_id"' \
        in ' '.join(query.from_clause.code.split())


def test_nulls_on_a_delegated_many2one_put_the_null_test_first(environment):
    city = _model(environment, 'test_orm.city')
    code, _query_ = _order(city, 'country_id asc nulls last')
    assert code.startswith('"test_orm_city"."country_id" IS NULL,')


def test_the_id_of_a_many2one_orders_by_the_column_without_a_join(environment):
    city = _model(environment, 'test_orm.city')
    code, query = _order(city, 'country_id.id')
    assert code == '"test_orm_city"."country_id"'
    assert 'JOIN' not in query.from_clause.code


def test_a_many2one_whose_comodel_orders_by_id_uses_the_column(environment):
    message = _model(environment, 'test_orm.message')
    code, query = _order(message, 'discussion desc')
    assert code == '"test_orm_message"."discussion" DESC'
    assert 'JOIN' not in query.from_clause.code


def test_a_many2one_cycle_stops(environment, monkeypatch):
    category = _model(environment, 'test_orm.category')
    monkeypatch.setattr(type(category), '_order', 'parent, name')
    code, _query_ = _order(category, 'parent')
    assert code == '"test_orm_category__parent"."name"'


def test_an_unknown_field_raises_value_error(environment):
    city = _model(environment, 'test_orm.city')
    with pytest.raises(ValueError, match="Invalid field 'nope'"):
        _order(city, 'nope')


def test_an_invalid_order_raises_user_error(environment):
    city = _model(environment, 'test_orm.city')
    with pytest.raises(UserError):
        _order(city, 'name; drop table x')
