"""``base.public_partner`` y ``base.public_user`` en cada base.

≙ ``odoo19c: odoo/addons/base/data/res_users_data.xml:28-37`` y
``res_partner_data.xml:27-30``. Sin ellos, el respaldo de
``Transaction.flush`` —volcar como usuario público cuando no hay
``default_env`` (``odoo/orm/environments.py:591-597``)— falla en cuanto se
recorre. Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/
designs/public-user-seed.md``.
"""
import pytest
import tests.conftest as conftest
from django.apps import apps
from django.db import DEFAULT_DB_ALIAS

from addons.base.data.res_users_data import public_user_seed, seed_public_user
from addons.base.models import IrModelData, ResCompany, ResUsers
from orm.environments import Environment, get_transaction

pytestmark = pytest.mark.django_db


def test_the_public_user_exists_archived_without_groups():
    user = IrModelData.ref('base.public_user')
    assert (user.login, user.active, user.name) == (
        'public', False, 'Public user')
    assert IrModelData.ref('base.public_partner') == user.partner
    assert user.partner.active is False
    assert not user.group_ids.exists()


def test_seeding_again_keeps_the_same_rows():
    before = ResUsers.objects.count()
    first = seed_public_user(apps, DEFAULT_DB_ALIAS)
    assert seed_public_user(apps, DEFAULT_DB_ALIAS).pk == first.pk
    assert ResUsers.objects.count() == before


def test_the_flush_catalogue_restores_it():
    assert public_user_seed in conftest._SEEDERS


def test_a_flush_without_default_env_writes_as_the_public_user(monkeypatch):
    """El respaldo de la fuente: lo pendiente sin dueño se vuelca."""
    with Environment('default'):
        company = ResCompany.objects.create(name='pub-flush',
                                            code='pub-flush')
    transaction = get_transaction()
    monkeypatch.setattr(transaction, 'default_env', None)
    transaction.flush()
    assert not transaction._has_pending()
    assert ResCompany.objects.filter(pk=company.pk).exists()
