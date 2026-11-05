"""``BaseModel.write`` — su entrada, ≙ ``odoo19c: odoo/orm/models.py``
(``write``, las líneas que preceden a ``_write``). TASK-API-0485.

Lo que se cualifica aquí es el contrato de entrada del recordset: vacío
devuelve ``True`` sin tocar nada; con registros, ``check_access('write')``
y el acceso por campo antes de escribir; un nombre que no es campo levanta
``ValueError``; y la escritura alcanza a **todos** los registros. El
volcado por lotes (``_write``, ``_write_multi``) sigue ausente.
"""
import pytest

from exceptions import AccessError
from orm.environments import Environment
from tests.factories.user_factory import UserFactory

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def _stored(records):
    rows = type(records)._default_manager.filter(pk__in=records.ids)
    return dict(rows.values_list("name", "active"))


def _two(env):
    return env["test_orm.model_active_field"].create(
        [{"name": "a", "active": True}, {"name": "b", "active": True}])


def test_write_on_an_empty_recordset_is_true(env):
    assert env["test_orm.model_active_field"].browse().write(
        {"active": False}) is True


def test_write_reaches_every_record(env):
    records = _two(env)
    assert records.write({"active": False}) is True
    assert _stored(records) == {"a": False, "b": False}


def test_write_checks_the_model_access_first(env):
    records = _two(env)
    with Environment(None, UserFactory().pk, {}) as plain:
        with pytest.raises(AccessError):
            records.with_env(plain).write({"active": False})
    assert _stored(records) == {"a": True, "b": True}


def test_write_refuses_a_name_that_is_not_a_field(env):
    records = _two(env)
    with pytest.raises(ValueError, match="Invalid field 'nope'"):
        records.write({"nope": 1})
