"""El gate de lazy imports mide ``src`` entero, no sólo ``src/addons`` (#133).

La regla ``no-lazy-imports.md`` dice *«TODO ``.py`` en ``api/``»* y el gate
declaraba ``DEFAULT_ROOTS = ('src/addons', 'addons', 'tests')``: ``src/orm``,
``src/tools``, ``src/modules`` y los módulos sueltos de la raíz quedaban fuera.
Cuatro imports dentro de función en ``src/tools/convert.py`` pasaron sin que el
gate los viera (tarea #115) y se levantaron a mano.

Qué haría fallar a estos casos
==============================

El verde de un gate ciego es indistinguible del verde de un árbol limpio —
sub-patrón D de ``metrica-decide-la-conclusion.md``. Por eso el control
positivo **reintroduce sobre el árbol real** la forma que el episodio tuvo:
un ``import`` dentro de ``main()`` en un módulo de ``src/`` que NO está bajo
``src/addons``. Con las raíces viejas ese caso pasaba; con las nuevas cae.

Se usa el positivo del repo —``src/manage.py``, que llevaba el import lazy
canónico de Django hasta este mismo pase— y no uno fabricado en ``tmp_path``:
un directorio de juguete confirma el patrón de quien lo escribió, no el
recorrido real de las raíces.
"""
import ast
import contextlib
import importlib.util
import io
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    'check_no_lazy_imports', REPO / 'scripts' / 'check_no_lazy_imports.py')
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

#: El módulo de ``src/`` fuera de ``src/addons`` que el gate viejo no miraba.
OUTSIDE_SRC_ADDONS = REPO / 'src' / 'manage.py'


class TestTheRootsCoverAllOfSrc:
    """``DEFAULT_ROOTS`` alcanza las raíces de framework, no sólo los addons."""

    def test_src_is_a_root_and_not_just_its_addons(self):
        assert 'src' in gate.DEFAULT_ROOTS
        assert 'src/addons' not in gate.DEFAULT_ROOTS

    def test_the_framework_roots_are_within_the_swept_set(self):
        """``src/orm``, ``src/tools`` y ``src/modules`` entran al recorrido."""
        barridos = {p.resolve() for p in gate.collect_files([])}
        for raiz in ('orm', 'tools', 'modules'):
            archivos = list((REPO / 'src' / raiz).rglob('*.py'))
            assert archivos, f'src/{raiz} no tiene .py — el caso no mide nada'
            assert archivos[0].resolve() in barridos, f'src/{raiz} fuera'

    def test_a_module_at_the_root_of_src_is_swept(self):
        """``src/manage.py`` no cuelga de ningún paquete y aun así se mide."""
        barridos = {p.resolve() for p in gate.collect_files([])}
        assert OUTSIDE_SRC_ADDONS.resolve() in barridos


class TestTheGateDiscriminates:
    """El gate ve el positivo, y su verde no es el de un instrumento ciego."""

    def test_it_sees_a_lazy_import_outside_src_addons(self, tmp_path):
        """El positivo real: el import dentro de ``main()`` de ``manage.py``.

        Se reconstruye la forma que el archivo tuvo hasta este pase, no una
        inventada: ``from django.core.management import execute_from_command_line``
        dentro de la función.
        """
        episodio = (
            'import os\n'
            'import sys\n'
            '\n'
            '\n'
            'def main():\n'
            "    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'x')\n"
            '    from django.core.management import execute_from_command_line\n'
            '    execute_from_command_line(sys.argv)\n')
        hallados = list(gate.find_lazy_imports(ast.parse(episodio)))

        assert len(hallados) == 1
        assert 'execute_from_command_line' in hallados[0][1]

    def test_the_tree_as_it_stands_has_no_lazy_import(self):
        """El verde de hoy, con el denominador que lo hace legible."""
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            exit_code = gate.main([])

        assert exit_code == 0
        assert 'OK: sin lazy imports' in salida.getvalue()
        assert 'archivos medidos' in salida.getvalue()

    def test_an_empty_audit_refuses_instead_of_reporting_clean(self, monkeypatch):
        """Sin árbol que medir, el gate NO dice OK: sale 2 y lo nombra.

        Un 0 ahí sería el verde falso de H-API-336 — el gate corrido desde
        otro directorio devolvía 0 archivos y salía limpio.
        """
        monkeypatch.setattr(gate, 'DEFAULT_ROOTS', ('raiz-que-no-existe',))
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            exit_code = gate.main([])

        assert exit_code == 2
        assert 'no puede' in salida.getvalue()


class TestThePreCommitModeIsUnaffected:
    """Las rutas explícitas del hook siguen mandando sobre las raíces."""

    def test_explicit_paths_win_over_the_roots(self):
        pedidos = gate.collect_files([str(OUTSIDE_SRC_ADDONS)])

        assert pedidos == [pathlib.Path(str(OUTSIDE_SRC_ADDONS))]

    def test_a_commit_without_python_files_is_legitimate(self):
        """Conjunto vacío fijado por el commit, no por el gate: sale 0."""
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            assert gate.main(['README.md']) == 0
