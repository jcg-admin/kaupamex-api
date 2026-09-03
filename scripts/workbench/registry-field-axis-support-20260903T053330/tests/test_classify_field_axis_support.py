"""El control del clasificador, escrito ANTES del instrumento.

Un clasificador que devolviera ``BUILDABLE`` sin mirar nada pasaria los ocho
simbolos y nadie lo notaria: el resultado es el esperado. Los dos casos que
discriminan son ``test_an_absent_primitive_blocks`` y
``test_an_absent_installed_symbol_is_not_ready`` — el instrumento tiene que
poder decir que NO.

Se corre con el paquete del banco en la ruta::

    DJANGO_SETTINGS_MODULE=config.settings.testing PYTHONPATH=src \
        uv run pytest scripts/workbench/registry-field-axis-support-20260903T053330/tests -q
"""
import importlib.util
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    'classify_field_axis_support', HERE / 'classify_field_axis_support.py')
classify_field_axis_support = importlib.util.module_from_spec(_spec)
sys.modules['classify_field_axis_support'] = classify_field_axis_support
_spec.loader.exec_module(classify_field_axis_support)

Symbol = classify_field_axis_support.Symbol
classify = classify_field_axis_support.classify
resolve = classify_field_axis_support.resolve
INVENTORY = classify_field_axis_support.INVENTORY
SYMBOLS = classify_field_axis_support.SYMBOLS


class TestResolve:
    """``resolve`` responde por un dotted path, no por su forma."""

    def test_a_module_resolves(self):
        assert resolve('collections') is True

    def test_an_attribute_of_a_module_resolves(self):
        assert resolve('collections.defaultdict') is True

    def test_an_attribute_of_a_class_resolves(self):
        assert resolve('collections.defaultdict.default_factory') is True

    def test_an_absent_module_does_not_resolve(self):
        assert resolve('no.existe.este.modulo') is False

    def test_an_absent_attribute_does_not_resolve(self):
        assert resolve('collections.no_existe_este_nombre') is False


class TestClassify:
    """Los tres cubos, y que el instrumento sepa decir que no."""

    def test_an_installed_symbol_is_ready(self):
        symbol = Symbol(
            name='fake_ready', reference='—', does='—',
            provider=('django', 'recorrido del arbol a dict'),
            installed=('collections.defaultdict',), primitives=())
        verdict = classify(symbol)
        assert verdict.kind == 'READY'
        assert verdict.missing == ()

    def test_only_primitives_is_buildable(self):
        symbol = Symbol(
            name='fake_buildable', reference='—', does='—',
            provider=('cpython', 'contencion por bytecode'),
            installed=(), primitives=('collections.defaultdict', 'warnings.warn'))
        verdict = classify(symbol)
        assert verdict.kind == 'BUILDABLE'
        assert verdict.missing == ()

    def test_an_absent_primitive_blocks(self):
        """El control: sin esto, un clasificador constante pasaria todo."""
        symbol = Symbol(
            name='fake_blocked', reference='—', does='—',
            provider=('cpython', 'contencion por bytecode'),
            installed=(), primitives=('collections.defaultdict', 'no.existe.nada'))
        verdict = classify(symbol)
        assert verdict.kind == 'BLOCKED'
        assert verdict.missing == ('no.existe.nada',)

    def test_an_absent_installed_symbol_is_not_ready(self):
        """Declarar ``installed`` no basta: tiene que resolver."""
        symbol = Symbol(
            name='fake_claimed', reference='—', does='—',
            provider=('django', 'recorrido del arbol a dict'),
            installed=('django.no_existe_este_nombre',),
            primitives=('collections.defaultdict',))
        verdict = classify(symbol)
        assert verdict.kind == 'BUILDABLE'


class TestDeclaredPopulation:
    """Los ocho simbolos del tramo, y su entrada en el INVENTORY."""

    def test_the_population_is_the_eight_of_the_reference(self):
        assert len(SYMBOLS) == 8

    def test_every_symbol_names_an_inventory_entry(self):
        for symbol in SYMBOLS:
            assert symbol.provider in INVENTORY, symbol.name

    def test_every_symbol_cites_its_reference_line(self):
        for symbol in SYMBOLS:
            assert symbol.reference.startswith('odoo19c: odoo/orm/registry.py:')

    def test_no_declared_symbol_is_blocked(self):
        """Si alguno saliera BLOCKED, el porte tendria un bloqueo medido."""
        bloqueados = [(v.name, v.missing) for v in map(classify, SYMBOLS)
                      if v.kind == 'BLOCKED']
        assert bloqueados == []


if __name__ == '__main__':
    sys.exit(pytest.main([__file__, '-q']))
