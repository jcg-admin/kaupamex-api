"""El verificador de premisa, medido por conducta y no por su nombre.

Tests **puros**: no tocan Django ni la base. Miden el instrumento sobre
árboles fabricados cuyo desenlace se conoce.

Tres controles discriminan, y los tres apuntan a un verde que no distingue:

- ``test_a_field_declared_by_assignment_is_seen`` — la forma que el gate
  hermano de ``docs`` **no puede ver**. Su índice sólo casa ``def``/``class``
  al principio de línea, y aquí hay **3127** campos declarados por asignación
  contra 11070 declaraciones de función o clase: el 22 % del universo, y
  justo la parte de la que hablan las fichas de porte. Sin este caso, un
  índice ciego a los campos publicaría «premisa firme» sobre una ficha que
  pide construir un campo que ya existe.
- ``test_an_empty_index_refuses_without_emitting_a_count`` — con el índice
  vacío **ninguna** ficha produce señal, así que el guion diría «0 piden
  re-encuadre» y parecería sano. Es H-API-335 otra vez: un gate apuntado a
  una raíz vacía publica su cero y nadie lo nota. Rehúsa con exit 2.
- ``test_naming_a_symbol_without_a_build_verb_is_not_a_signal`` — mencionar
  un símbolo no es afirmar que falta. Sin este caso la señal dispararía en
  toda ficha que cite código, y una señal que dispara siempre es una que
  nadie mira.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'scripts'))

from verify_premise import (  # noqa: E402
    build_symbol_index,
    premise_of_manifest,
    signals_for_text,
)

DONE = 'completed'


@pytest.fixture
def tree(tmp_path):
    """Un árbol mínimo con las dos formas de declaración que el árbol usa."""
    module = tmp_path / 'src' / 'addons' / 'probe'
    module.mkdir(parents=True)
    (module / 'models.py').write_text(
        'from django.db import models\n'
        'import fields\n'
        '\n'
        '\n'
        'class ProbeModel(models.Model):\n'
        '    barcode_number = fields.Char("Barcode")\n'
        '\n'
        '    def compute_probe_total(self):\n'
        '        return 0\n',
        encoding='utf-8')
    return tmp_path


@pytest.fixture
def symbols(tree):
    index, files = build_symbol_index([tree / 'src'])
    assert files == 1, 'el árbol de prueba tiene un solo archivo'
    return index


class TestTheIndexSeesBothDeclarationForms:

    def test_a_function_is_seen(self, symbols):
        assert 'compute_probe_total' in symbols

    def test_a_class_is_seen(self, symbols):
        assert 'ProbeModel' in symbols

    def test_a_field_declared_by_assignment_is_seen(self, symbols):
        """El caso que el índice de ``docs`` no puede ver."""
        assert 'barcode_number' in symbols

    def test_each_entry_carries_its_form_and_place(self, symbols):
        kind, where = symbols['barcode_number'][0]
        assert kind == 'campo'
        assert where.endswith('models.py:6')

    def test_a_local_variable_is_not_a_declaration(self, tree):
        """Sólo cuenta lo declarado al nivel de la clase, no un local."""
        (tree / 'src' / 'loose.py').write_text(
            'def run():\n    helper_value = 1\n    return helper_value\n',
            encoding='utf-8')
        index, _ = build_symbol_index([tree / 'src'])
        assert 'helper_value' not in index


class TestTheSymbolSignal:

    def test_a_build_verb_over_a_declared_symbol_signals(self, symbols):
        found = signals_for_text(
            'Portar compute_probe_total, que falta en el arbol', symbols)
        assert [code for code, _ in found] == ['S1']

    def test_a_declared_field_signals_too(self, symbols):
        found = signals_for_text('Construir barcode_number en el modelo', symbols)
        assert [code for code, _ in found] == ['S1']

    def test_naming_a_symbol_without_a_build_verb_is_not_a_signal(self, symbols):
        found = signals_for_text(
            'Medir como se comporta compute_probe_total bajo carga', symbols)
        assert found == []

    def test_an_undeclared_symbol_is_not_a_signal(self, symbols):
        found = signals_for_text('Portar compute_absent_thing en el modelo', symbols)
        assert found == []

    def test_a_symbol_declared_everywhere_is_common_vocabulary(self, tree):
        for number in range(4):
            (tree / 'src' / f'many{number}.py').write_text(
                'def name_get(self):\n    return 1\n', encoding='utf-8')
        index, _ = build_symbol_index([tree / 'src'])
        assert signals_for_text('Portar name_get en el modelo', index) == []


class TestThePathSignal:

    def test_a_cited_path_that_does_not_exist_signals(self, symbols, tree):
        found = signals_for_text(
            'Portar lo que falta en src/orm/absent_module.py', symbols,
            path_roots=[tree])
        assert [code for code, _ in found] == ['S2']

    def test_a_cited_path_that_exists_is_silent(self, symbols, tree):
        found = signals_for_text(
            'Revisar src/addons/probe/models.py', symbols, path_roots=[tree])
        assert found == []


class TestTheBlockerSignal:

    def test_a_closed_blocker_signals(self, symbols):
        tasks = {'42': {'status': DONE, 'subject': 'ya cerrada'}}
        found = signals_for_text(
            'Esta tarea esta bloqueada por #42 y no puede avanzar',
            symbols, tasks=tasks)
        assert [code for code, _ in found] == ['S3']

    def test_an_open_blocker_is_silent(self, symbols):
        tasks = {'42': {'status': 'pending', 'subject': 'sigue abierta'}}
        found = signals_for_text(
            'Esta tarea esta bloqueada por #42 y no puede avanzar',
            symbols, tasks=tasks)
        assert found == []

    def test_without_a_board_the_blocker_signal_is_not_emitted(self, symbols):
        """Sin tablero no se puede decidir, y no decidir NO es «no hay»."""
        found = signals_for_text(
            'Esta tarea esta bloqueada por #42', symbols, tasks=None)
        assert found == []


class TestTheWorkbenchManifestIsASource:
    """La pieza de banco es la segunda fuente, y por eso el motor toma texto."""

    def test_it_reads_the_question_and_the_corrected_premise(self, tmp_path):
        pieza = tmp_path / 'algo-20260101T000000'
        pieza.mkdir()
        (pieza / 'manifest.json').write_text(json.dumps({
            'question': 'Portar compute_probe_total',
            'corrected_premise': 'la cifra era otra cosa',
            'metric': 'no se lee',
        }), encoding='utf-8')
        text = premise_of_manifest(pieza / 'manifest.json')
        assert 'compute_probe_total' in text
        assert 'la cifra era otra cosa' in text
        assert 'no se lee' not in text

    def test_a_manifest_premise_produces_the_same_signal(self, tmp_path, symbols):
        pieza = tmp_path / 'algo-20260101T000000'
        pieza.mkdir()
        (pieza / 'manifest.json').write_text(
            json.dumps({'question': 'Construir barcode_number desde cero'}),
            encoding='utf-8')
        found = signals_for_text(premise_of_manifest(pieza / 'manifest.json'),
                                 symbols)
        assert [code for code, _ in found] == ['S1']


class TestItRefusesInsteadOfPublishingAZero:

    def test_an_empty_index_refuses_without_emitting_a_count(self, tmp_path):
        """Sin símbolos, un 0 no distingue «premisa firme» de «no pude medir»."""
        with pytest.raises(SystemExit) as salida:
            build_symbol_index([tmp_path / 'no-existe'], require_files=True)
        assert salida.value.code == 2

    def test_without_the_guard_it_would_have_published_the_zero(self, tmp_path):
        """El control del control: sin ``require_files`` el índice sale vacío
        y ninguna señal dispara — que es exactamente el verde falso."""
        index, files = build_symbol_index([tmp_path / 'no-existe'])
        assert (index, files) == ({}, 0)
        assert signals_for_text('Portar compute_probe_total', index) == []
