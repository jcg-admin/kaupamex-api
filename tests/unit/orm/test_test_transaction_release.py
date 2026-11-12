"""El cierre de cada prueba devuelve la transacción del ORM a su estado.

Lo que la prueba fija —su ``default_env``— no sobrevive a su ``rollback``:
si lo hiciera, la prueba siguiente volcaría como un usuario que la base ya
no tiene (gate del lote 3, ``res_partner.write_uid``).
"""
import pytest

from orm.environments import (Environment, _discard_connection_transaction,
                              get_transaction)
from tests.conftest import release_test_transaction

pytestmark = pytest.mark.django_db


def test_the_default_env_fixed_by_a_test_does_not_survive_it():
    before = get_transaction()
    default_env = before.default_env
    before.default_env = None
    Environment(uid=987654)
    assert before.default_env._uid_override == 987654
    release_test_transaction(before, default_env)
    assert get_transaction() is before
    assert before.default_env is default_env


def test_a_transaction_created_by_the_test_is_discarded():
    before = get_transaction()
    default_env = before.default_env
    _discard_connection_transaction()
    created = get_transaction()
    Environment(uid=987654)
    release_test_transaction(before, default_env)
    assert get_transaction() is not created
    assert get_transaction().default_env is None
