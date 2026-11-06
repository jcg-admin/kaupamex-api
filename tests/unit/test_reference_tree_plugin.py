"""La marca ``reference``: quién la recibe, cuándo omite y qué se reporta.

``tests/fixtures/reference_tree.py`` decide con un solo criterio si una
prueba que depende de ``odoo19c`` puede ejecutarse. Estos casos fijan las
cuatro piezas por separado; la medición de conjunto —la suite completa con y
sin la referencia— vive en el banco
``scripts/workbench/reference-dependent-tests-20261105T232809``.

*Métrica:* resultado de cada pieza sobre items e informes construidos aquí.
*Ciega a:* el orden real de hooks de pytest y la ejecución con ``-n``; eso
lo mide la ejecución de la población en el banco, no estos casos.
"""
import types

import pytest

from tests.fixtures import reference_tree

pytestmark = pytest.mark.unit


class Item:
    """Lo que la marca lee de un item: sus fixtures y sus marcas."""

    def __init__(self, fixturenames, marked=False):
        self.fixturenames = fixturenames
        self.markers = ['reference'] if marked else []

    def get_closest_marker(self, name):
        return name if name in self.markers else None

    def add_marker(self, name):
        self.markers.append(name)


def report(when='setup', marked=True, skipped=False):
    keywords = {'reference': 1} if marked else {}
    return types.SimpleNamespace(when=when, keywords=keywords, skipped=skipped)


class TestTheFixtureCarriesTheMarker:

    def test_a_test_asking_for_the_fixture_is_marked(self):
        items = [Item(['reference', 'monkeypatch']), Item(['monkeypatch'])]
        assert reference_tree.mark_items(items) == 1
        assert items[0].markers == ['reference']
        assert items[1].markers == []

    def test_an_explicit_marker_is_not_doubled(self):
        item = Item(['reference'], marked=True)
        assert reference_tree.mark_items([item]) == 0
        assert item.markers == ['reference']


class TestTheTreeDecidesTheSkip:

    def test_an_existing_directory_runs(self, tmp_path):
        assert reference_tree.missing_reason(tmp_path) is None

    def test_an_absent_directory_names_its_path(self, tmp_path):
        absent = tmp_path / 'odoo-tools'
        reason = reference_tree.missing_reason(absent)
        assert reason.startswith('referencia ausente:')
        assert str(absent) in reason

    def test_a_marked_test_is_skipped_without_the_tree(
            self, tmp_path, monkeypatch):
        monkeypatch.setattr(reference_tree, 'reference_root',
                            lambda: tmp_path / 'absent')
        with pytest.raises(pytest.skip.Exception):
            reference_tree.pytest_runtest_setup(Item([], marked=True))

    def test_an_unmarked_test_is_never_skipped(self, tmp_path, monkeypatch):
        monkeypatch.setattr(reference_tree, 'reference_root',
                            lambda: tmp_path / 'absent')
        assert reference_tree.pytest_runtest_setup(Item([])) is None


class TestTheCountReadsReports:

    def test_only_setup_reports_of_marked_tests_count(self):
        count = reference_tree.ReferenceCount()
        for each in (report(), report(when='call'), report(marked=False),
                     report(skipped=True)):
            count.pytest_runtest_logreport(each)
        assert (count.marked, count.skipped) == (2, 1)


class TestTheSummarySaysWhatWasNotVerified:

    def test_no_marked_test_prints_nothing(self, tmp_path):
        assert reference_tree.summary_line(0, 0, tmp_path) is None

    def test_a_present_tree_reports_the_population(self, tmp_path):
        line = reference_tree.summary_line(257, 0, tmp_path)
        assert line == (
            f'referencia: 257 pruebas marcadas, árbol presente en {tmp_path}')

    def test_an_absent_tree_says_the_contracts_were_not_verified(
            self, tmp_path):
        line = reference_tree.summary_line(257, 257, tmp_path / 'absent')
        assert '257 de 257' in line
        assert 'no existe' in line
        assert 'NO se verificaron' in line

    def test_skips_with_the_tree_present_point_to_their_reasons(
            self, tmp_path):
        line = reference_tree.summary_line(10, 3, tmp_path)
        assert 'los motivos, con -rs' in line
        assert 'NO se verificaron' in line
