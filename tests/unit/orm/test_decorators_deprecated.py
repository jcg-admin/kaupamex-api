"""``deprecated`` de ``odoo19c: odoo/orm/decorators.py:13-50`` y su enlace en
``api`` (``odoo19c: odoo/api/__init__.py``). TASK-API-0485.

Desde Python 3.13 la fuente usa ``warnings.deprecated``; antes declara una
versión simplificada con el mismo contrato. Las dos ramas se prueban: este
árbol admite ``>=3.12``.
"""
import importlib.util
import pathlib
import warnings

import pytest

import api
from orm import decorators
from orm.types import Self

SOURCE = pathlib.Path(decorators.__file__)


def _decorators_without_warnings_deprecated(monkeypatch):
    """Carga el módulo como lo vería Python 3.12: sin
    ``warnings.deprecated``."""
    monkeypatch.delattr(warnings, 'deprecated', raising=False)
    spec = importlib.util.spec_from_file_location('decorators_312', SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_api_exposes_the_orm_deprecated():
    assert api.deprecated is decorators.deprecated


def test_api_exposes_self():
    assert api.Self is Self


@pytest.mark.parametrize('flavour', ['native', 'fallback'])
def test_deprecated_warns_and_still_calls(flavour, monkeypatch):
    module = decorators if flavour == 'native' else \
        _decorators_without_warnings_deprecated(monkeypatch)

    @module.deprecated('use other()')
    def old(value):
        return value + 1

    with pytest.warns(DeprecationWarning, match='use other'):
        assert old(1) == 2
    assert old.__deprecated__ == 'use other()'


@pytest.mark.parametrize('flavour', ['native', 'fallback'])
def test_deprecated_without_category_only_marks(flavour, monkeypatch):
    module = decorators if flavour == 'native' else \
        _decorators_without_warnings_deprecated(monkeypatch)

    def old():
        return 3

    marked = module.deprecated('gone', category=None)(old)
    with warnings.catch_warnings():
        warnings.simplefilter('error')
        assert marked() == 3
    assert marked.__deprecated__ == 'gone'


def test_fallback_rejects_a_message_that_is_not_text(monkeypatch):
    module = _decorators_without_warnings_deprecated(monkeypatch)
    with pytest.raises(TypeError, match="type str for 'message'"):
        module.deprecated(42)


REFERENCE_FACADE = {
    'NewId', 'autovacuum', 'constrains', 'depends', 'depends_context',
    'deprecated', 'model', 'model_create_multi', 'onchange', 'ondelete',
    'private', 'readonly', 'Environment', 'SUPERUSER_ID', 'ContextType',
    'DomainType', 'IdType', 'Self', 'ValuesType',
}


def test_api_facade_matches_the_reference_names():
    """``odoo19c: odoo/api/__init__.py`` liga estos nombres y ninguno más:
    ``returns`` vive en ``odoo18c: odoo/api.py`` y la 19 lo retiró."""
    assert set(api.__all__) == REFERENCE_FACADE
    assert not hasattr(api, 'returns')
