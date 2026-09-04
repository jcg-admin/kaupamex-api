"""Control del lector de FLUJO de la referencia (tarea #352).

El defecto que el guion ataca lo registro ``H-API-1072``: se porta el simbolo,
se lee su cuerpo, y el contrato que gobierna vive **fuera** — en una base, en
quien lo llama, o en un hermano que declara el mismo nombre. Ningun gate del
arbol lo ve: los que hay miden presencia, cabecera, sitio o nombre.

Los casos usan **positivos reales de la referencia**, no fabricados: quien
escribe el instrumento no puede validarlo con su propio encuadre
(``hallazgo-abierto-genera-sucesor.md``). Los tres controles de regresion
reproducen los tres defectos que el guion tuvo mientras se escribia:

1. una **clase** se reportaba como "no se declara" — el extractor solo juntaba
   funciones, asi que un cero falso;
2. una clase se contaba como **llamadora** de las llamadas de sus propios
   metodos, y cada llamador salia dos veces;
3. los **hermanos** daban cero justo donde mas hay, porque cada declaracion se
   excluia contra si misma.

Los tres son la misma forma: un resultado que no discrimina *"el fenomeno no
ocurre"* de *"el instrumento no lo ve"* (``metrica-decide-la-conclusion.md``,
sub-patron D).
"""
import importlib.util
import io
import contextlib
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    'reference_flow', REPO / 'scripts' / 'reference_flow.py')
reference_flow = importlib.util.module_from_spec(_spec)
sys.modules['reference_flow'] = reference_flow
_spec.loader.exec_module(reference_flow)

counterpart_body = sys.modules['counterpart_body']
reference_roots = sys.modules['reference_roots']

#: Las dos raices que estos casos miden. Se declaran aqui para que el
#: denominador del test sea explicito, igual que lo es el del informe.
ROOTS = ('odoo/orm', 'odoo/tools')


@pytest.fixture(scope='module')
def index():
    """El indice de las dos raices, construido una vez para todos los casos."""
    return reference_flow.index_roots(reference_flow.resolve_roots(ROOTS))


@pytest.fixture(scope='module')
def tree_root():
    return reference_roots.tree()


class TestTheExtractorSeesClassesAndAssignments:
    """Regresion 1 — una clase reportada como no declarada es un cero falso.

    ``frozendict`` es una **clase** de ``odoo/tools/misc.py``. Con el extractor
    que solo juntaba funciones, el informe decia "no se declara en el alcance
    medido" de un simbolo que si estaba: el instrumento no lo veia y el
    resultado se leia como ausencia.
    """

    def test_a_class_is_declared(self, index):
        found = reference_flow.declarations_named(index, 'frozendict')
        assert found, 'frozendict se declara en odoo/tools/misc.py'
        assert {decl.kind for _, decl in found} == {'class'}

    def test_a_module_level_assignment_is_declared(self, index):
        found = reference_flow.declarations_named(index, 'EMPTY_DICT')
        assert [decl.kind for _, decl in found] == ['assign']


class TestTheSymbolIsReadAcrossItsWholeFamily:
    """Unidad 1 y 4 — ``convert_to_column`` lo declaran quince clases.

    Es el positivo que la tarea #351 ya nombraba por su cuenta: portarlo
    mirando una sola clase es leer un quinceavo del contrato.
    """

    def test_fifteen_declarations_in_ten_files(self, index):
        found = reference_flow.declarations_named(index, 'convert_to_column')
        assert len(found) == 15
        assert len({path for path, _ in found}) == 10

    def test_the_siblings_are_not_empty(self, index):
        # Regresion 3: excluir cada declaracion contra si misma daba cero.
        assert len(reference_flow.siblings_of(
            index, 'convert_to_column')) == 15

    def test_the_origin_file_stops_being_its_own_sibling(self, index,
                                                         tree_root):
        origin = tree_root / 'odoo/orm/fields.py'
        siblings = reference_flow.siblings_of(
            index, 'convert_to_column', origin)
        assert 'Field' not in siblings
        assert len(siblings) == 14


class TestTheBasesCarryTheContract:
    """Unidad 2 — el contrato puede vivir arriba en la jerarquia."""

    def test_the_declaring_bases_are_reported(self, index):
        flow = reference_flow.flow_of('convert_to_column', index)
        owners = {decl.owner for _, decl in flow.bases_declaring}
        assert owners == {'Field', 'Selection', 'BaseString'}


class TestTheCallersAreMethodsNotTheirClasses:
    """Regresion 2 — la clase no es llamadora de lo que llaman sus metodos.

    ``ast.walk`` sobre un ``ClassDef`` ve las llamadas de cada metodo, asi que
    sin el filtro la clase duena sale ademas del metodo y el numerador se
    infla. Medido con la guarda anulada sobre estas dos raices: los sitios de
    ``frozendict`` pasan de 6 a 9, y los tres que aparecen son exactamente
    ``Environment``, ``Property`` y ``BaseModel`` — las clases de metodos que
    ya estaban en la lista.
    """

    def test_a_real_caller_edge_exists(self, index):
        flow = reference_flow.flow_of('frozendict', index)
        callers = {site.caller for site in flow.callers}
        assert 'freehash' in callers, sorted(callers)
        assert '__hash__' in callers, sorted(callers)

    def test_the_owning_classes_are_not_counted_as_callers(self, index):
        flow = reference_flow.flow_of('frozendict', index)
        callers = {site.caller for site in flow.callers}
        assert 'Environment' not in callers
        assert 'Property' not in callers

    def test_no_call_site_is_a_class_declaration(self, index):
        flow = reference_flow.flow_of('convert_to_column', index)
        classes = {(str(path), decl.lineno)
                   for path, (_, decls) in index.items()
                   for decl in decls if decl.kind == 'class'}
        assert not [s for s in flow.callers
                    if (s.path, s.lineno) in classes]

    def test_the_symbol_is_not_its_own_caller(self, index):
        flow = reference_flow.flow_of('convert_to_column', index)
        own = {(str(path), decl.lineno) for path, decl in flow.declarations}
        assert not [s for s in flow.callers if (s.path, s.lineno) in own]


class TestTheReportDeclaresWhatItMeasuredAndWhatItCannotSee:
    """Un conteo sin denominador no es un resultado."""

    def test_the_scope_carries_the_denominator(self, index):
        flow = reference_flow.flow_of('convert_to_column', index)
        assert flow.scope.files_parsed == len(index)
        assert flow.scope.declarations == len(flow.declarations)

    def test_the_universe_is_not_the_files_that_survived_the_prefilter(self):
        # Publicar una sola cifra confundiria "cuanto se midio" con "de
        # cuantos se leyo el AST" — el sub-patron A, un encabezado unico
        # sobre dos metricas. Con prefiltro las dos son distintas.
        roots = reference_flow.resolve_roots(('odoo/tools',))
        files = reference_flow.universe_files(roots)
        narrow = reference_flow.index_files(
            reference_flow.files_naming(files, ('frozendict',)))
        flow = reference_flow.flow_of(
            'frozendict', narrow, universe=len(files))
        assert flow.scope.files_in_universe == len(files)
        assert flow.scope.files_parsed < flow.scope.files_in_universe

    def test_every_unit_is_printed_even_when_empty(self, index, tree_root):
        # Una unidad ausente del informe se lee como "no aplica"; una vacia,
        # como "medido, no hay". Por eso las cuatro salen siempre.
        text = reference_flow.render(
            reference_flow.flow_of('frozendict', index), tree_root)
        for label in ('declara', 'bases con el', 'lo llaman', 'hermanos'):
            assert label in text

    def test_a_symbol_absent_from_the_scope_says_so(self, index, tree_root):
        text = reference_flow.render(
            reference_flow.flow_of('nombre_que_no_existe_en_la_referencia',
                                   index), tree_root)
        assert 'no se declara en el alcance medido' in text

    def test_the_run_publishes_its_blind_spots(self, capsys):
        assert reference_flow.main(
            ['--symbol', 'frozendict', '--root', 'odoo/tools']) == 0
        out = capsys.readouterr().out
        assert 'alcance medido:' in out
        assert 'Ciega a:' in out


class TestThePrefilterWidensTheScopeWithoutLosingEdges:
    """El prefiltro es lo que hace medible el arbol entero.

    Dos controles, y los dos pueden fallar: que no pierda aristas —si las
    perdiera, el conjunto reducido daria menos llamadores que el completo— y
    que el alcance ancho encuentre al consumidor que el estrecho no ve.
    """

    def test_the_prefilter_keeps_every_edge_the_full_index_finds(self, index):
        # Control: si ``files_naming`` descartara un archivo con arista, el
        # conjunto de llamadores encogeria. Se compara contra el indice
        # completo de las mismas raices, que es el instrumento sin filtro.
        roots = reference_flow.resolve_roots(ROOTS)
        files = reference_flow.universe_files(roots)
        narrow = reference_flow.index_files(
            reference_flow.files_naming(files, ('convert_to_column',)))
        completo = reference_flow.flow_of('convert_to_column', index)
        filtrado = reference_flow.flow_of('convert_to_column', narrow)
        assert {(s.path, s.lineno) for s in filtrado.callers} \
            == {(s.path, s.lineno) for s in completo.callers}
        assert len(narrow) < len(index)

    def test_the_narrow_scope_publishes_a_zero_the_wide_scope_refutes(self):
        # El episodio que motivo el prefiltro: con las tres raices de
        # framework, ``parse_inline_template`` solo se ve llamado por su
        # propio archivo; el consumidor de verdad vive en ``addons/mail``.
        # Ese informe no decia "nadie mas lo llama" sino "el alcance no
        # llega a quien lo llama".
        estrechas = reference_flow.resolve_roots(
            ('odoo/tools', 'odoo/orm', 'odoo/addons/base'))
        estrecho = reference_flow.index_roots(
            estrechas, names=('parse_inline_template',))
        dentro = reference_flow.callers_of(
            estrecho, 'parse_inline_template',
            reference_flow.declarations_named(
                estrecho, 'parse_inline_template'))
        assert [s for s in dentro if 'mail_render_mixin' in s.path] == []
        assert {pathlib.Path(s.path).name for s in dentro} \
            == {'rendering_tools.py'}

        anchas = reference_flow.resolve_roots(reference_flow.DEFAULT_ROOTS)
        ancho = reference_flow.index_roots(
            anchas, names=('parse_inline_template',))
        sitios = reference_flow.callers_of(
            ancho, 'parse_inline_template',
            reference_flow.declarations_named(ancho, 'parse_inline_template'))
        assert [s for s in sitios if 'mail_render_mixin' in s.path]


class TestTheGuardCanFail:
    """Una raiz inexistente rehusa con exit 2 y NO emite informe.

    Un ``0 llamadores`` sobre un alcance vacio seria un verde falso: no
    distingue "nadie lo llama" de "no habia donde mirar".
    """

    def test_a_missing_root_refuses_without_a_report(self, capsys):
        code = reference_flow.main(
            ['--symbol', 'frozendict', '--root', 'odoo/no-existe'])
        captured = capsys.readouterr()
        assert code == 2
        assert 'raiz inexistente' in captured.err
        assert captured.out == ''

    def test_a_missing_file_refuses(self, capsys):
        code = reference_flow.main(['--file', 'odoo/tools/no-existe.py'])
        assert code == 2
        assert 'no existe' in capsys.readouterr().err
