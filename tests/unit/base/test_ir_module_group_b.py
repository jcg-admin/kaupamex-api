"""Grupo B de ``ir.module.module``: recorridos, ``has_iap`` y borrado.

≙ ``odoo19c: odoo/addons/base/models/ir_module.py:326,333-345,532-580``.
Diseño: ``designs/ir-module-group-b.md``.
"""

import pytest

from addons.base.models import IrModule, IrModuleDependency
from exceptions import UserError
from orm.environments import Environment
from orm.utils import SUPERUSER_ID

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def _modules():
    return Environment(uid=SUPERUSER_ID)['ir.module.module']


def _module(name, state='uninstalled', depends=()):
    module = IrModule.objects.create(name=name, shortdesc=name, state=state)
    for dependency in depends:
        IrModuleDependency.objects.create(module_id=module, name=dependency)
    return _modules().browse(module.id)


@pytest.fixture
def chain():
    """``gb_c`` → ``gb_b`` → ``gb_a``; ``gb_d`` → ``gb_a``."""
    return {
        'a': _module('gb_a', 'installed'),
        'b': _module('gb_b', 'installed', ['gb_a']),
        'c': _module('gb_c', 'uninstalled', ['gb_b']),
        'd': _module('gb_d', 'to remove', ['gb_a']),
    }


def test_downstream_takes_a_recordset_and_returns_one(chain):
    # ``m.id NOT IN known_deps.ids or self.ids`` (``:548``): ``gb_b`` está
    # en ``self`` y no vuelve, aunque dependa de ``gb_a``.
    reached = (chain['a'] | chain['b']).downstream_dependencies(
        exclude_states=())
    assert set(reached.mapped('name')) == {'gb_c', 'gb_d'}


def test_downstream_default_excludes_uninstalled_and_to_remove(chain):
    assert chain['a'].downstream_dependencies().mapped('name') == ['gb_b']


def test_upstream_default_excludes_installed_and_to_remove(chain):
    assert not chain['c'].upstream_dependencies()
    # El ``JOIN ir_module_module m ON (d.module_id=m.id)`` (``:569``)
    # sólo alcanza módulos con dependencias propias: ``gb_a`` no declara
    # ninguna y no aparece, como ``base`` en la fuente.
    assert chain['c'].upstream_dependencies(
        exclude_states=('',)).mapped('name') == ['gb_b']


def test_known_deps_are_kept_and_not_walked_again(chain):
    reached = chain['c'].upstream_dependencies(
        known_deps=chain['d'], exclude_states=('',))
    assert set(reached.mapped('name')) == {'gb_b', 'gb_d'}


def test_an_empty_recordset_returns_itself():
    empty = _modules().browse()
    assert empty.downstream_dependencies() is empty


def test_has_iap_follows_the_upstream_tree(chain):
    # ``iap`` declara dependencias en la fuente (``web``); sin ellas el
    # ``JOIN`` de ``upstream_dependencies`` no lo alcanzaría.
    if not IrModule.objects.filter(name='iap').exists():
        _module('iap', 'installed', ['gb_a'])
    with_iap = _module('gb_with_iap', 'uninstalled', ['iap'])
    assert with_iap.has_iap is True
    assert chain['c'].has_iap is False


def test_unlinking_an_installed_module_is_refused(chain):
    with pytest.raises(UserError):
        chain['b'].unlink()
    assert IrModule.objects.filter(name='gb_b').exists()


def test_an_uninstalled_module_can_be_unlinked():
    module = _module('gb_gone', 'uninstalled')
    module.unlink()
    assert not IrModule.objects.filter(name='gb_gone').exists()
