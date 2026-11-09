"""``Field._description_sortable`` por el mecanismo de la referencia.

≙ ``odoo19c: odoo/orm/fields.py:909-922``: un campo almacenado con columna es
ordenable; uno heredado responde por el suyo; el resto, si
``_order_field_to_sql`` lo puede ordenar sin ``ValueError`` ni
``AccessError``. Diseño en ``designs/description-sortable.md`` del Workbench.

*Métrica:* el booleano que ``fields_get`` publica como ``sortable``.
*Ciega a:* la ejecución del ``ORDER BY``.
"""
import pytest
from django.contrib.auth import get_user_model

from orm.environments import env as current_env
from orm.environments import sudo, user_scope

pytestmark = pytest.mark.django_db


@pytest.fixture
def environment():
    user = get_user_model().objects.create_user(
        login='description-sortable', password=None, name='u')
    with user_scope(user.pk), sudo():
        yield current_env()


def _sortable(environment, model_name, field_name):
    model = environment[model_name]
    return model._fields[field_name]._description_sortable(environment)


def test_a_stored_column_is_sortable(environment):
    assert _sortable(environment, 'test_orm.category', 'name') is True


def test_a_non_stored_related_field_is_sortable(environment):
    assert _sortable(environment, 'test_orm.related', 'foo_name') is True


def test_a_computed_field_without_column_is_not_sortable(environment):
    assert _sortable(environment, 'test_orm.category', 'depth') is False
