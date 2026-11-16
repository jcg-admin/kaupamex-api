"""``persist_gate_evidence.py reclaim``: las fases MARK RECLAIMABLE y CLEANUP.

Una copia del scratchpad se retira sólo si su contenido es, byte a byte, el
de un archivo del banco que el índice registra y que está en ``HEAD`` sin
cambios locales, y si ningún proceso la tiene abierta. Diseño:
``outputs/storage-audit-20261116.md`` §10.

Uso: ``python3 -m pytest -q -c /dev/null -p no:cacheprovider <este archivo>``
(fuera del ``pytest.ini`` del proyecto, que exige pytest-django).
"""
import csv
import importlib.util
import pathlib
import subprocess

import pytest

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    'persist_gate_evidence', HERE / 'persist_gate_evidence.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def _git(repo, *args):
    subprocess.run(['git', '-C', str(repo), *args], check=True,
                   capture_output=True)


@pytest.fixture
def bench(tmp_path, monkeypatch):
    repo = tmp_path / 'repo'
    bench = repo / 'bench'
    (bench / 'outputs' / 'gates').mkdir(parents=True)
    _git(repo, 'init', '-q')
    _git(repo, 'config', 'user.email', 'test@example.invalid')
    _git(repo, 'config', 'user.name', 'test')
    monkeypatch.chdir(repo)
    monkeypatch.setattr(module, '_open_paths', lambda paths: set())
    return repo, bench


def _persist(repo, bench, source, commit=True):
    module.main(str(bench), 'gate-x', 'full-suite', 'abc', '-', '-',
                str(source))
    if commit:
        _git(repo, 'add', '.')
        _git(repo, 'commit', '-q', '-m', 'persist')


def _scratch(tmp_path, name='suite.log', body='3 passed in 1s\n'):
    source = tmp_path / 'scratch' / name
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(body)
    return source


def _ledger(bench):
    path = bench / 'outputs' / 'gates' / 'reclaimed.tsv'
    with path.open() as handle:
        return list(csv.DictReader(handle, delimiter='\t'))


def test_a_persisted_and_committed_copy_is_removed(bench, tmp_path):
    repo, bench = bench
    source = _scratch(tmp_path)
    _persist(repo, bench, source)
    module.reclaim(str(bench), str(source))
    assert not source.exists()
    [row] = _ledger(bench)
    assert row['decision'] == 'removed'
    assert row['bank_file'].endswith('gate-x/suite.log')


def test_mark_only_records_without_removing(bench, tmp_path):
    repo, bench = bench
    source = _scratch(tmp_path)
    _persist(repo, bench, source)
    module.reclaim(str(bench), '--mark-only', str(source))
    assert source.exists()
    assert _ledger(bench)[0]['decision'] == 'reclaimable'


def test_an_uncommitted_bank_copy_keeps_the_source(bench, tmp_path):
    repo, bench = bench
    source = _scratch(tmp_path)
    _persist(repo, bench, source, commit=False)
    module.reclaim(str(bench), str(source))
    assert source.exists()
    assert _ledger(bench)[0]['decision'] == 'kept:not-in-head'


def test_a_source_that_changed_after_persisting_is_kept(bench, tmp_path):
    repo, bench = bench
    source = _scratch(tmp_path)
    _persist(repo, bench, source)
    source.write_text('3 passed in 1s\nmore\n')
    module.reclaim(str(bench), str(source))
    assert source.exists()
    assert _ledger(bench)[0]['decision'] == 'kept:not-in-index'


def test_the_same_name_with_other_content_is_kept(bench, tmp_path):
    """Un nombre igual no basta: decide el contenido."""
    repo, bench = bench
    _persist(repo, bench, _scratch(tmp_path))
    other = _scratch(tmp_path / 'b', body='9 failed in 1s\n')
    module.reclaim(str(bench), str(other))
    assert other.exists()
    assert _ledger(bench)[0]['decision'] == 'kept:not-in-index'


def test_a_bank_copy_modified_in_the_tree_keeps_the_source(bench, tmp_path):
    repo, bench = bench
    source = _scratch(tmp_path)
    _persist(repo, bench, source)
    (bench / 'outputs' / 'gates' / 'gate-x' / 'suite.log').write_text('x')
    module.reclaim(str(bench), str(source))
    assert source.exists()
    assert _ledger(bench)[0]['decision'] == 'kept:bank-modified'


def test_an_open_source_is_kept(bench, tmp_path, monkeypatch):
    repo, bench = bench
    source = _scratch(tmp_path)
    _persist(repo, bench, source)
    monkeypatch.setattr(module, '_open_paths',
                        lambda paths: {str(source.resolve())})
    module.reclaim(str(bench), str(source))
    assert source.exists()
    assert _ledger(bench)[0]['decision'] == 'kept:open'
