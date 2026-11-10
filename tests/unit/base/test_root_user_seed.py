"""``base.user_root`` y ``base.partner_root`` — el superusuario sembrado.

≙ ``odoo19c: odoo/addons/base/data/base_data.sql:134`` y
``res_users_data.xml:5-11``: la fila ``SUPERUSER_ID`` con login
``__system__``, archivada, y sus dos XML-ID. Diseño:
``designs/module-install-cycle.md``, L4e (e5).
"""
import pytest
import tests.conftest as conftest
from django.apps import apps
from django.db import DEFAULT_DB_ALIAS

from addons.base.data.res_users_data import seed, seed_root_user
from addons.base.models import IrModelData, ResUsers
from orm.utils import SUPERUSER_ID

pytestmark = pytest.mark.django_db


def test_the_superuser_row_exists_archived():
    root = ResUsers.objects.get(pk=SUPERUSER_ID)
    assert (root.login, root.active, root.partner.active) == (
        '__system__', False, False)


def test_its_external_ids_point_to_it():
    root = ResUsers.objects.get(pk=SUPERUSER_ID)
    assert IrModelData.ref('base.user_root') == root
    assert IrModelData.ref('base.partner_root') == root.partner


def test_seeding_again_keeps_the_same_rows():
    before = ResUsers.objects.count()
    assert seed_root_user(apps, DEFAULT_DB_ALIAS).pk == SUPERUSER_ID
    assert ResUsers.objects.count() == before


def test_the_next_user_does_not_collide_with_it():
    """La secuencia avanza tras el id explícito — ≙ ``select setval``."""
    user = ResUsers.objects.create_user(
        login='root-seed-next', password=None, name='Siguiente')
    assert user.pk != SUPERUSER_ID


def test_the_flush_catalogue_restores_it():
    """Un ``flush`` borra la fila y ``django_migrations`` sigue dando 0106
    por aplicada: el catálogo de tests la repone (``_SEEDERS``)."""
    assert seed in conftest._SEEDERS
    IrModelData.objects.filter(
        module='base', name__in=('user_root', 'partner_root')).delete()
    # La baja del superusuario está prohibida (``unlink``); el ``flush``
    # la salta igual que este borrado crudo.
    ResUsers.objects.filter(pk=SUPERUSER_ID)._raw_delete(DEFAULT_DB_ALIAS)
    seed()
    assert IrModelData.ref('base.user_root').pk == SUPERUSER_ID
