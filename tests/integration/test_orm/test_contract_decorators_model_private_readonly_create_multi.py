"""Contrato de ``model``, ``private``, ``readonly`` y ``model_create_multi``
— ``odoo19c: odoo/orm/decorators.py:313-371``.

Oráculo diferencial: se ejecuta el ``decorators.py`` de la referencia (sólo
depende de la biblioteca estándar), compilado desde su texto para no escribir
``__pycache__`` en ``odoo-tools``, y se compara con el nuestro aplicando cada
decorador a funciones de muestra. Las aserciones literales repiten lo leído
del cuerpo de la referencia.

Mutaciones que lo hacen caer: ``model`` sin la rama de ``create``
(``:323-324``); ``private`` o ``readonly`` sin su marca; ``model_create_multi``
que no envuelve un ``Mapping`` en lista.
"""
import pathlib
import types

import pytest

import reference_roots
from orm import decorators

pytestmark = pytest.mark.integration

REFERENCE_FILE = (reference_roots.tree('odoo19c')
                  / 'odoo' / 'orm' / 'decorators.py')
MARKS = ('_api_model', '_api_private', '_readonly')


def _reference_decorators():
    source = pathlib.Path(REFERENCE_FILE).read_text()
    module = types.ModuleType('reference_orm_decorators')
    exec(compile(source, str(REFERENCE_FILE), 'exec'), module.__dict__)
    return module


def _samples():
    def create(self, vals_list):
        return ('create', vals_list)

    def action(self, value=None):
        return ('action', value)

    return {'create': create, 'action': action}


def _behaviour(module):
    rows = []
    for decorator in ('model', 'private', 'readonly', 'model_create_multi'):
        for name, function in _samples().items():
            result = getattr(module, decorator)(function)
            marks = tuple(getattr(result, mark, None) for mark in MARKS)
            calls = (result(None, {'a': 1}), result(None, [{'a': 1}]))
            rows.append((decorator, name, result is function,
                         result.__name__, marks, calls))
    return rows


@pytest.mark.reference
@pytest.mark.skipif(
    not REFERENCE_FILE.is_file(),
    reason=f'referencia ausente: {REFERENCE_FILE} no existe (odoo-tools no '
           'montado; ver referencia-odoo-gobierna-las-decisiones.md)')
class TestDecoratorsBehaveLikeTheReference:

    def test_every_decorator_matches_the_reference_module(self):
        expected = _behaviour(_reference_decorators())
        observed = _behaviour(decorators)
        mismatches = [(e, o) for e, o in zip(expected, observed) if e != o]
        assert not mismatches, mismatches[:3]


class TestDecoratorsLiteralContract:

    def test_model_marks_a_plain_method(self):
        def action(self):
            return None
        assert decorators.model(action) is action
        assert action._api_model is True

    def test_model_turns_create_into_the_multi_wrapper(self):
        def create(self, vals_list):
            return vals_list
        wrapped = decorators.model(create)
        assert wrapped is not create
        assert wrapped._api_model is True
        assert wrapped(None, {'a': 1}) == [{'a': 1}]

    def test_private_and_readonly_mark_the_same_function(self):
        def action(self):
            return None
        assert decorators.private(action) is action
        assert action._api_private is True
        assert decorators.readonly(action) is action
        assert action._readonly is True

    def test_create_multi_lists_a_single_mapping(self):
        def create(self, vals_list):
            return vals_list
        wrapped = decorators.model_create_multi(create)
        assert wrapped(None, {'a': 1}) == [{'a': 1}]
        assert wrapped(None, [{'a': 1}]) == [{'a': 1}]
        assert wrapped.__name__ == 'create'
