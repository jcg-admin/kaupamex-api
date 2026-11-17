"""La resiembra tras un test transaccional vuelca como superusuario.

La carga de datos de la fuente corre con un entorno de superusuario
(``odoo19c: odoo/modules/loading.py:404``), así que su volcado no recurre al
usuario público (``odoo19c: odoo/orm/environments.py:591-597``). Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
reseed-default-environment.md``.

El positivo es el fallo real de la suite completa: sembrar ``base.user_root``
deja campos sucios y los vuelca antes de que exista ``base.public_user``.
"""
import pytest
import tests.conftest as conftest

from addons.base.models import IrModelData, ResCompany
from orm.environments import get_transaction
from orm.registry import clear_all_caches

pytestmark = pytest.mark.django_db


def _dirty_seeder():
    """Como ``root_user_seed``: un alta que deja campos sucios y el volcado
    que su ``commit`` dispara."""
    ResCompany.objects.create(name='reseed-probe', code='reseed-probe')
    get_transaction().flush()


def test_reseeding_does_not_need_the_public_user(monkeypatch):
    transaction = get_transaction()
    monkeypatch.setattr(transaction, 'default_env', None)
    IrModelData.objects.filter(module='base', name='public_user').delete()
    clear_all_caches()
    conftest.reseed((_dirty_seeder,))
    assert not transaction._has_pending()
    assert ResCompany.objects.filter(code='reseed-probe').exists()
