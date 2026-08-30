"""El gate del banco de trabajo, medido por conducta y no por su nombre.

Estos tests son **puros**: no tocan Django ni la base. Miden el instrumento
sobre directorios fabricados cuyo desenlace se conoce.

Dos controles discriminan, y los dos apuntan a un verde que no distingue:

- ``test_a_key_present_but_empty_is_an_offence`` — una clave declarada y vacia
  PARECE declarada. Un gate que solo comprobara ``key not in declared`` la
  daria por buena, y su verde no distinguiria «lo declaro» de «puso la clave
  para pasar el gate».
- ``test_without_the_schema_it_refuses_without_emitting_a_count`` — sin el
  esquema, un 0 no distingue «todo cumple» de «no pude medir». El gate rehusa
  con exit 2 y sin cifra, en vez de publicar el cero.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'scripts'))

from check_workbench import (  # noqa: E402
    offences_of,
    required_keys,
    work_dirs,
)

CONFORMING = {
    'question': 'que declara cada gate que suprime, y cuanto',
    'instrument': 'inventory_frozen_debt.py',
    'metric': 'lineas de cada archivo *baseline*.txt que un gate consulta',
    'blind_to': ['un gate que suprima por una lista embebida en el guion'],
    'destination': 'docs: source/gestion/pm/api/.../hallazgos/',
}


def make_work(root: Path, name: str, manifest=None, *, raw=None) -> Path:
    """Crea una pieza de trabajo minima bajo ``root``."""
    work = root / name
    work.mkdir(parents=True)
    if raw is not None:
        (work / 'manifest.json').write_text(raw)
    elif manifest is not None:
        (work / 'manifest.json').write_text(json.dumps(manifest))
    return work


class TestRequiredKeys:
    """Las obligatorias salen del esquema, no de una copia en el gate."""

    def test_it_reads_the_five_from_the_schema(self):
        assert required_keys() == [
            'question', 'instrument', 'metric', 'blind_to', 'destination']

    def test_without_the_schema_it_refuses_without_emitting_a_count(
            self, tmp_path, capsys):
        """EL CONTROL. Un 0 sin esquema no distingue «todo cumple» de «no pude
        medir» — el sub-patron D de ``metrica-decide-la-conclusion.md``."""
        with pytest.raises(SystemExit) as salida:
            required_keys(tmp_path / 'no-existe.json')
        assert salida.value.code == 2
        error = capsys.readouterr().err
        assert 'verde falso' in error
        # Y NO emite conteo: la palabra «incumplidor» no aparece.
        assert 'incumplidor' not in error


class TestOffences:
    """Que le falta a una pieza de trabajo."""

    def test_a_conforming_manifest_has_no_offence(self, tmp_path):
        work = make_work(tmp_path, 'inventario-20260830T193000', CONFORMING)
        assert offences_of(work, list(CONFORMING)) == []

    @pytest.mark.parametrize('missing', list(CONFORMING))
    def test_each_missing_key_is_caught(self, tmp_path, missing):
        incomplete = {k: v for k, v in CONFORMING.items() if k != missing}
        work = make_work(tmp_path, f'sin-{missing}', incomplete)
        found = offences_of(work, list(CONFORMING))
        assert found == [f"falta la clave obligatoria '{missing}'"]

    @pytest.mark.parametrize('empty', ['', [], {}, None])
    def test_a_key_present_but_empty_is_an_offence(self, tmp_path, empty):
        """EL CONTROL QUE DISCRIMINA. Una clave vacia parece declarada.

        Un gate que solo comprobara ``key not in declared`` la daria por
        buena. Cae si alguien simplifica la condicion.
        """
        hollow = dict(CONFORMING, blind_to=empty)
        work = make_work(tmp_path, f'vacia-{type(empty).__name__}', hollow)
        assert offences_of(work, list(CONFORMING)) == [
            "la clave 'blind_to' esta vacia"]

    def test_a_missing_manifest_is_named_not_skipped(self, tmp_path):
        work = make_work(tmp_path, 'sin-manifiesto')
        assert offences_of(work, list(CONFORMING)) == [
            'no declara manifest.json']

    def test_broken_json_is_named_not_skipped(self, tmp_path):
        """Un JSON roto no se traga en silencio: silenciarlo lo convierte en
        el mismo verde falso que el esquema ausente."""
        work = make_work(tmp_path, 'json-roto', raw='{no es json')
        found = offences_of(work, list(CONFORMING))
        assert len(found) == 1
        assert found[0].startswith('manifest.json no es JSON valido')

    def test_a_json_that_is_not_an_object_is_caught(self, tmp_path):
        work = make_work(tmp_path, 'lista', raw='["question"]')
        assert offences_of(work, list(CONFORMING)) == [
            'manifest.json no declara un objeto']


class TestWorkDirs:
    """Que cuenta como pieza de trabajo y que es del propio banco."""

    def test_the_bench_own_files_are_not_work(self, tmp_path):
        (tmp_path / 'README.md').write_text('la convencion')
        (tmp_path / 'manifest_schema.json').write_text('{}')
        make_work(tmp_path, 'trabajo-20260830T193000', CONFORMING)
        assert [d.name for d in work_dirs(tmp_path)] == [
            'trabajo-20260830T193000']

    def test_hidden_and_cache_directories_are_not_work(self, tmp_path):
        (tmp_path / '__pycache__').mkdir()
        (tmp_path / '.oculto').mkdir()
        assert work_dirs(tmp_path) == []

    def test_an_absent_bench_gives_an_empty_list_not_an_error(self, tmp_path):
        assert work_dirs(tmp_path / 'no-existe') == []
