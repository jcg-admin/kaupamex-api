"""UID cache dependencies retain the privilege axis required by Odoo.

Only actual Field metadata and Environment cache keys are exercised here.
The attached-record descriptor has separate integration controls.
"""

import pytest

import fields
from orm import registry
from orm.environments import env, transaction_scope


@pytest.fixture(autouse=True)
def isolated_transaction():
    with transaction_scope():
        yield


def uid_field(monkeypatch, compute_sudo):
    field = fields.Boolean(compute='_unused', compute_sudo=compute_sudo)
    monkeypatch.setattr(registry, 'field_depends_context', {field: ('uid',)})
    return field


@pytest.mark.parametrize('superuser', [False, True])
def test_non_sudo_compute_keys_actor_and_privilege(monkeypatch, superuser):
    field = uid_field(monkeypatch, compute_sudo=False)
    environment = env()(user=17, su=superuser)
    assert environment.cache_key(field) == ((17, superuser),)


def test_sudo_compute_shares_the_privilege_axis_only(monkeypatch):
    field = uid_field(monkeypatch, compute_sudo=True)
    ordinary = env()(user=17, su=False)
    elevated = env()(user=17, su=True)
    assert ordinary.cache_key(field) == elevated.cache_key(field) == (17,)


@pytest.mark.parametrize('compute_sudo', [False, True])
def test_different_actors_do_not_share_keys(monkeypatch, compute_sudo):
    field = uid_field(monkeypatch, compute_sudo)
    first = env()(user=17, su=False)
    second = env()(user=18, su=False)
    assert first.cache_key(field) != second.cache_key(field)
