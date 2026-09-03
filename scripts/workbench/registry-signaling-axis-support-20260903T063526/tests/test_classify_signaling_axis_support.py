"""Casos del clasificador del eje de senalizacion, escritos ANTES del instrumento.

El instrumento reparte los siete simbolos que la referencia declara entre
``setup_signaling`` (``odoo19c: odoo/orm/registry.py:1036``) y ``cursor``
(``:1165``) en los dos cubos que el criterio fija: **el stack lo trae hecho**
—hay un simbolo instalado y basta llamarlo— y **el stack tiene con que
construirlo** —no hay simbolo hecho, pero las primitivas estan y no hace falta
ninguna dependencia de fuera—.

**El control que discrimina** es ``test_a_missing_primitive_blocks``: sin el,
un clasificador que devolviera BUILDABLE siempre pasaria todos los demas casos.
"""
import importlib.util
import pathlib
import sys

import pytest

_HERE = pathlib.Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location(
    'classify_signaling_axis_support', _HERE / 'classify_signaling_axis_support.py')
classifier = importlib.util.module_from_spec(_SPEC)
sys.modules['classify_signaling_axis_support'] = classifier
_SPEC.loader.exec_module(classifier)

READY = classifier.READY
BUILDABLE = classifier.BUILDABLE
BLOCKED = classifier.BLOCKED


class TestResolve:
    """``resolve`` dice si un dotted path existe, sin importar el arbol entero."""

    def test_a_stdlib_symbol_resolves(self):
        assert classifier.resolve('contextlib.contextmanager') is not None

    def test_an_attribute_chain_resolves(self):
        assert classifier.resolve('django.db.connections') is not None

    def test_an_invented_module_does_not(self):
        assert classifier.resolve('no_existe_este_modulo.nada') is None

    def test_an_invented_attribute_of_a_real_module_does_not(self):
        assert classifier.resolve('contextlib.no_existe_este_atributo') is None


class TestClassify:
    """El reparto en los tres cubos."""

    def test_all_installed_resolving_is_ready(self):
        symbol = classifier.Symbol(
            name='x', reference='odoo19c: :1', installed=['contextlib.closing'],
            primitives=[], inventory=('cpython', 'evaluación y control de flujo'))
        assert classifier.classify(symbol).bucket == READY

    def test_no_installed_but_primitives_is_buildable(self):
        symbol = classifier.Symbol(
            name='x', reference='odoo19c: :1', installed=[],
            primitives=['contextlib.contextmanager'],
            inventory=('cpython', 'evaluación y control de flujo'))
        assert classifier.classify(symbol).bucket == BUILDABLE

    def test_a_missing_primitive_blocks(self):
        """El control: sin este caso, devolver BUILDABLE siempre pasaria."""
        symbol = classifier.Symbol(
            name='x', reference='odoo19c: :1', installed=[],
            primitives=['no_existe_este_modulo.nada'],
            inventory=('cpython', 'evaluación y control de flujo'))
        verdict = classifier.classify(symbol)
        assert verdict.bucket == BLOCKED
        assert 'no_existe_este_modulo.nada' in verdict.missing

    def test_a_missing_installed_falls_back_to_the_primitives(self):
        """Un ``installed`` que no resuelve NO bloquea: se construye."""
        symbol = classifier.Symbol(
            name='x', reference='odoo19c: :1',
            installed=['no_existe_este_modulo.nada'],
            primitives=['contextlib.contextmanager'],
            inventory=('cpython', 'evaluación y control de flujo'))
        assert classifier.classify(symbol).bucket == BUILDABLE

    def test_the_verdict_carries_its_inventory_entry(self):
        symbol = classifier.Symbol(
            name='x', reference='odoo19c: :1', installed=[],
            primitives=['contextlib.contextmanager'],
            inventory=('cpython', 'evaluación y control de flujo'))
        assert classifier.classify(symbol).inventory in classifier.INVENTORY


class TestTheDeclaredPopulation:
    """Los siete simbolos del tramo, y nada mas."""

    def test_it_declares_the_seven_symbols(self):
        assert len(classifier.SYMBOLS) == 7

    def test_every_symbol_names_its_reference_line(self):
        assert all(symbol.reference.startswith('odoo19c: ')
                   for symbol in classifier.SYMBOLS)

    def test_every_symbol_declares_an_inventory_entry_that_exists(self):
        assert all(symbol.inventory in classifier.INVENTORY
                   for symbol in classifier.SYMBOLS)

    def test_no_symbol_declares_a_dependency_outside_the_inventory(self):
        """El criterio lo exige: no hace falta ninguna dependencia de fuera."""
        allowed = {origin for origin, _tema in classifier.INVENTORY}
        assert allowed >= {symbol.inventory[0] for symbol in classifier.SYMBOLS}


class TestReport:
    """El informe agrega por cubo."""

    def test_it_counts_every_symbol_once(self):
        report = classifier.report()
        assert sum(len(names) for names in report.values()) == len(classifier.SYMBOLS)

    def test_the_three_buckets_are_always_present(self):
        assert set(classifier.report()) == {READY, BUILDABLE, BLOCKED}


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))
