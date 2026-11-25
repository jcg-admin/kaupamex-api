"""``_load_manifest`` normaliza el manifest como la fuente.

≙ ``odoo19c: odoo/modules/module.py:415-467``. ``initialize`` lee
``auto_install`` ya normalizado (``odoo/modules/db.py:82``), así que estos
casos son la precondición de ``designs/orm-modules-db-initialize-0058.md``.
La mitad de versiones queda fuera: la serie del puerto colisiona con dos
manifests (addendum del diseño).
"""
import pytest

from modules.module import _load_manifest


def test_auto_install_true_becomes_the_set_of_depends():
    manifest = _load_manifest(
        'bridge', {'depends': ['portal', 'auth_totp'], 'auto_install': True})
    assert manifest['auto_install'] == {'portal', 'auth_totp'}


def test_an_auto_install_list_becomes_a_set():
    manifest = _load_manifest(
        'bridge', {'depends': ['portal', 'auth_totp'],
                   'auto_install': ['portal']})
    assert manifest['auto_install'] == {'portal'}


def test_an_empty_auto_install_list_stays_an_empty_set():
    """``[]`` significa «instalar siempre» (``module.py:445-449``)."""
    manifest = _load_manifest('always', {'depends': ['base'],
                                         'auto_install': []})
    assert manifest['auto_install'] == set()


def test_an_auto_install_trigger_outside_depends_is_refused():
    with pytest.raises(AssertionError, match='auto_install triggers'):
        _load_manifest('bridge', {'depends': ['portal'],
                                  'auto_install': ['website']})


def test_auto_install_false_is_left_alone():
    assert _load_manifest('plain', {'depends': ['base']})[
        'auto_install'] is False


def test_empty_depends_fall_back_to_base():
    assert _load_manifest('leaf', {'depends': []})['depends'] == ['base']


def test_base_never_depends_on_anything():
    assert _load_manifest('base', {'depends': ['web']})['depends'] == []


def test_a_missing_license_defaults_to_lgpl3():
    assert _load_manifest('plain', {})['license'] == 'LGPL-3'


def test_mutating_one_manifest_does_not_leak_into_the_next():
    """La fuente copia el default en profundidad (``module.py:421``)."""
    first = _load_manifest('first', {})
    first['countries'].append('mx')
    assert _load_manifest('second', {})['countries'] == []
