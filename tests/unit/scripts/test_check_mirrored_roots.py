"""El gate de raíces espejadas ve un archivo entero sin contraparte (tarea #334).

Estos tests son **puros**: no tocan Django ni la base. Miden el instrumento,
no el árbol — mismo criterio que ``test_check_porte_completo.py`` y
``test_check_addon_root.py``: la prueba que sirve es contra un **positivo
conocido del repo**, no contra un caso fabricado por quien escribió el
patrón (``hallazgo-abierto-genera-sucesor.md``).

El positivo conocido es el episodio ``H-API-569``/``H-API-578``: se inventó
``src/orm/model_naming.py`` (y ``model_extension.py``), que la referencia no
declara. Los tests de "control positivo" reproducen exactamente esa forma
sobre el árbol real del repo — no un directorio de juguete.
"""
import importlib.util
import io
import contextlib
import pathlib
import shutil

import pytest

REPO = pathlib.Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    'check_mirrored_roots', REPO / 'scripts' / 'check_mirrored_roots.py')
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)


# --- list_py_files: qué cuenta como archivo comparable ---------------------


def make_py_tree(root: pathlib.Path, *paths: str) -> pathlib.Path:
    """Crea ``root/<path>`` para cada ruta relativa, con contenido mínimo."""
    for rel in paths:
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('# stub for a test\n')
    return root


def test_list_py_files_returns_relative_paths(tmp_path):
    root = make_py_tree(tmp_path, 'a.py', 'sub/b.py')

    assert gate.list_py_files(root) == {'a.py', 'sub/b.py'}


def test_list_py_files_excludes_pycache_at_any_depth(tmp_path):
    root = make_py_tree(
        tmp_path, 'a.py', '__pycache__/a.py', 'sub/__pycache__/b.py',
    )

    assert gate.list_py_files(root) == {'a.py'}


def test_list_py_files_excludes_migrations_as_framework_mechanism(tmp_path):
    """``migrations/`` es de Django, nunca tiene contraparte — no es defecto."""
    root = make_py_tree(tmp_path, 'models.py', 'migrations/0001_initial.py')

    assert gate.list_py_files(root) == {'models.py'}


def test_list_py_files_on_missing_root_does_not_explode(tmp_path):
    """Un lado del par que aún no existe mide vacío, no falla (H-API-569 lo
    pide: el lado 'ours' o 'reference' puede faltar sin tumbar el gate)."""
    assert gate.list_py_files(tmp_path / 'missing') == set()


# --- compare_root: las dos direcciones, nunca mezcladas ---------------------


def test_healthy_tree_reports_neither_direction(tmp_path):
    ours = make_py_tree(tmp_path / 'ours', 'a.py', 'b.py')
    reference = make_py_tree(tmp_path / 'reference', 'a.py', 'b.py')

    our_files, ref_files, gaps, without_counterpart = gate.compare_root(ours, reference)

    assert gaps == []
    assert without_counterpart == []
    assert len(our_files) == 2 and len(ref_files) == 2


def test_porting_gap_direction_a(tmp_path):
    """La referencia declara algo que nosotros aún no portamos."""
    ours = make_py_tree(tmp_path / 'ours', 'a.py')
    reference = make_py_tree(tmp_path / 'reference', 'a.py', 'b.py')

    _, _, gaps, without_counterpart = gate.compare_root(ours, reference)

    assert gaps == ['b.py']
    assert without_counterpart == []


def test_without_counterpart_is_the_h_api_569_shape(tmp_path):
    """La forma exacta del episodio: un archivo nuestro que la referencia no
    declara — el defecto que ``check_porte_completo.py`` no podía ver."""
    ours = make_py_tree(tmp_path / 'ours', 'registry.py', 'model_naming.py')
    reference = make_py_tree(tmp_path / 'reference', 'registry.py')

    _, _, gaps, without_counterpart = gate.compare_root(ours, reference)

    assert gaps == []
    assert without_counterpart == ['model_naming.py']


def test_both_directions_report_independently(tmp_path):
    """Un hueco y una posible invención simultáneos en la misma raíz se
    reportan ambos — no se compensan entre sí, no son "lo mismo con signo
    distinto"."""
    ours = make_py_tree(tmp_path / 'ours', 'model_naming.py')
    reference = make_py_tree(tmp_path / 'reference', 'registry.py')

    _, _, gaps, without_counterpart = gate.compare_root(ours, reference)

    assert gaps == ['registry.py']
    assert without_counterpart == ['model_naming.py']


def test_a_file_moved_to_another_subdir_is_not_matched_by_basename(tmp_path):
    """Ciega a la relocación: un archivo movido de sitio aparece en las DOS
    direcciones, no se reconoce como "el mismo archivo, en otro lado" — es
    la forma segura declarada en el docstring del gate."""
    ours = make_py_tree(tmp_path / 'ours', 'sub/models.py')
    reference = make_py_tree(tmp_path / 'reference', 'models.py')

    _, _, gaps, without_counterpart = gate.compare_root(ours, reference)

    assert gaps == ['models.py']
    assert without_counterpart == ['sub/models.py']


# --- baseline: sólo declara la dirección (b) --------------------------------


def test_load_baseline_skips_comments_and_blank_lines(tmp_path, monkeypatch):
    baseline_file = tmp_path / 'baseline.txt'
    baseline_file.write_text(
        '# a comment\n'
        '\n'
        'src/orm/routers.py::multi-DB routing\n'
    )
    monkeypatch.setattr(gate, 'BASELINE_PATH', baseline_file)

    assert gate.load_baseline() == {'src/orm/routers.py': 'multi-DB routing'}


def test_load_baseline_missing_file_is_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, 'BASELINE_PATH', tmp_path / 'missing.txt')

    assert gate.load_baseline() == {}


# --- select_roots: nunca "barre todo" ante una ruta desconocida ------------


def test_no_arguments_sweeps_every_root(monkeypatch):
    fake_roots = [('r1', pathlib.Path('/a'), pathlib.Path('/b')),
                  ('r2', pathlib.Path('/c'), pathlib.Path('/d'))]
    monkeypatch.setattr(gate, 'all_mirrored_roots', lambda: fake_roots)

    assert gate.select_roots([]) == fake_roots


def test_a_known_path_selects_only_that_root(tmp_path, monkeypatch):
    r1 = tmp_path / 'r1'
    r2 = tmp_path / 'r2'
    r1.mkdir()
    r2.mkdir()
    fake_roots = [('r1', r1, tmp_path / 'ref1'), ('r2', r2, tmp_path / 'ref2')]
    monkeypatch.setattr(gate, 'all_mirrored_roots', lambda: fake_roots)

    selected = gate.select_roots([str(r1)])

    assert selected == [fake_roots[0]]


def test_unknown_path_is_skipped_never_falls_back_to_sweep_all(tmp_path, monkeypatch):
    """Pedir una ruta que no es ninguna raíz espejada NUNCA cae de vuelta al
    barrido completo — eso sería exactamente el anti-patrón que la regla de
    diseño del gate prohíbe."""
    r1 = tmp_path / 'r1'
    r1.mkdir()
    fake_roots = [('r1', r1, tmp_path / 'ref1')]
    monkeypatch.setattr(gate, 'all_mirrored_roots', lambda: fake_roots)

    buffer = io.StringIO()
    with contextlib.redirect_stderr(buffer):
        selected = gate.select_roots([str(tmp_path / 'not-a-root')])

    assert selected == []
    assert 'no es una raíz espejada conocida' in buffer.getvalue()


# --- addon_roots: sólo pares que EXISTEN de los dos lados -------------------


def test_addon_roots_skips_an_l0_only_addon(tmp_path, monkeypatch):
    """Un addon nuestro sin par en la referencia (p. ej. ``authz``) no es una
    raíz espejada — no hay "sitio correcto" que comparar contra la nada.

    Se parcha ``_addon_root``, **no** ``REFERENCE_ROOT``. Desde H-DOCS-507 la
    resolución del addon de la referencia ya no compone
    ``REFERENCE_ROOT / 'addons'``: la delega en ``reference_roots.addon_root``,
    porque Community reparte sus addons en DOS raíces y componer una sola
    dejaba fuera del barrido a todo addon cuya contraparte viva en
    ``odoo/addons/``. Parchar la constante dejó de gobernar la resolución, así
    que este caso medía el árbol real en vez de su propio fixture — y pasaba a
    rojo sin que ninguna aserción lo explicara. Ver :ref:`h-api-901`.
    """
    repo = tmp_path / 'repo'
    reference = tmp_path / 'reference'
    (repo / 'addons' / 'shared').mkdir(parents=True)
    (repo / 'addons' / 'l0_only').mkdir(parents=True)
    (reference / 'addons' / 'shared').mkdir(parents=True)
    # 'l0_only' NO existe del lado de la referencia — a propósito.

    monkeypatch.setattr(gate, 'REPO', repo)
    monkeypatch.setattr(gate, '_addon_root',
                        lambda name, alias: reference / 'addons' / name)

    labels = sorted(label for label, _, _ in gate.addon_roots())

    assert labels == ['addons/shared']


# --- control positivo: el árbol REAL del repo, no uno fabricado ------------

_REFERENCE_TREE_PRESENT = gate.REFERENCE_ROOT.is_dir()
_SRC_ORM_PRESENT = (REPO / 'src' / 'orm').is_dir()


@pytest.mark.skipif(not (_REFERENCE_TREE_PRESENT and _SRC_ORM_PRESENT),
                    reason='requiere el árbol de referencia clonado (ODOO19C) '
                           'y src/orm del propio repo')
def test_src_orm_is_clean_against_the_real_baseline():
    """``src/orm`` contra la referencia REAL, con el baseline REAL del repo:
    0 huecos y 0 invenciones nuevas — los cuatro conocidos quedan declarados."""
    ours = REPO / 'src' / 'orm'
    reference = gate.REFERENCE_ROOT / 'odoo' / 'orm'
    baseline = gate.load_baseline()

    _, _, gaps, without_counterpart = gate.compare_root(ours, reference)
    new = [rel for rel in without_counterpart
          if gate.repo_relative_path(ours / rel) not in baseline]

    assert gaps == []
    assert new == []


@pytest.mark.skipif(not (_REFERENCE_TREE_PRESENT and _SRC_ORM_PRESENT),
                    reason='requiere el árbol de referencia clonado (ODOO19C) '
                           'y src/orm del propio repo')
def test_reproduces_h_api_569_on_the_real_tree(tmp_path):
    """Reproduce el episodio EXACTO —``model_naming.py`` inventado en
    ``src/orm``— pero copiando el árbol real a un ``tmp_path`` en vez de
    escribir en el repo: el gate lo marca como SIN CONTRAPARTE nueva."""
    ours = tmp_path / 'orm'
    shutil.copytree(REPO / 'src' / 'orm', ours,
                     ignore=shutil.ignore_patterns('__pycache__'))
    (ours / 'model_naming.py').write_text('# invented, H-API-569\n')
    reference = gate.REFERENCE_ROOT / 'odoo' / 'orm'
    baseline = gate.load_baseline()

    _, _, gaps, without_counterpart = gate.compare_root(ours, reference)
    new = [rel for rel in without_counterpart
          if gate.repo_relative_path(REPO / 'src' / 'orm' / rel) not in baseline]

    assert gaps == []
    assert new == ['model_naming.py']
