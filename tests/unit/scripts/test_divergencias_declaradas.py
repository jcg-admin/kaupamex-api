"""El registro de divergencias declaradas y su consumo por el gate de porte.

``porte-completo-no-parcial.md`` enumera tres desenlaces validos para un
simbolo que no se porta. El (2), bloqueo con sucesor, ya tenia hogar en
``check_bloqueo_declarado.py``; el (1), divergencia de mecanismo, vivia en el
docstring del archivo que la cometia — 417 archivos la declaran en prosa y el
gate de cobertura no podia ver ninguna.

La forma se adapta de ``coreutils: util/gnu-unfixable-tests.txt``: la lista por
nombre de lo que la reimplementacion nunca va a satisfacer, con motivo por
entrada, consumida por el instrumento.

Los tests son **puros**: miden el instrumento, no la aplicacion. Y el positivo
es del repo, no fabricado — ``base_sparse_field/models/models.py::Base::
_valid_field_parameter``, cuya divergencia esta medida en ``api@0a9a0fb`` con
el ``TypeError`` que la sustenta.
"""
import importlib.util
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    'check_porte_completo', REPO / 'scripts' / 'check_porte_completo.py')
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

#: El positivo real: entrada viva del registro al escribir estos tests.
REAL_POSITIVE = 'base_sparse_field/models/models.py::Base::_valid_field_parameter'


def test_the_registry_exists_and_is_not_empty():
    """Un registro ausente o vacio haria que todo el resto pase por vacuidad."""
    assert gate.DECLARED_DIVERGENCES.is_file()
    assert gate.load_divergences(), (
        'registro vacio: los tests de abajo pasarian sin medir nada')


def test_the_real_positive_is_declared():
    assert REAL_POSITIVE in gate.load_divergences()


def test_comments_do_not_enter_as_entries():
    """El `#` abre comentario, y la cabecera es casi todo el archivo."""
    for key in gate.load_divergences():
        assert not key.startswith('#')
        assert key


def test_every_entry_has_a_reason_above_it():
    """Una entrada sin motivo es una absolucion, no una declaracion.

    Se exige al menos un renglon de comentario NO vacio inmediatamente antes.
    """
    lines = gate.DECLARED_DIVERGENCES.read_text(encoding='utf-8').splitlines()
    for i, line in enumerate(lines):
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        previous = [l for l in lines[:i][::-1]]
        previous_one = next((l for l in previous if l.strip()), '')
        assert previous_one.lstrip().startswith('#'), (
            f'la entrada «{line.strip()}» no lleva motivo encima')


def test_the_three_key_granularities():
    keys = gate.keys_of('acme', 'foo.py', 'Bar', 'baz')
    assert keys == (
        'acme/models/foo.py::Bar::baz',
        'acme/models/foo.py::Bar',
        'acme/models/foo.py',
    )


def _finding(symbols):
    return [('acme', 'foo.py', 'Bar', 'MÉTODOS AUSENTES', list(symbols))]


def test_the_declared_leaves_the_debt_and_enters_its_own_count():
    debt, declared, used = gate.split_declared(
        _finding(['baz']), {'acme/models/foo.py::Bar::baz'})
    assert debt == []
    assert declared[0][4] == ['baz']
    assert used == {'acme/models/foo.py::Bar::baz'}


def test_a_symbol_entry_does_NOT_absolve_the_whole_class():
    """El criterio de `CLASE EXTENDIDA`: nunca se absuelve de mas."""
    debt, declared, _ = gate.split_declared(
        _finding(['baz', 'qux']), {'acme/models/foo.py::Bar::baz'})
    assert debt[0][4] == ['qux'], 'el pendiente tiene que sobrevivir'
    assert declared[0][4] == ['baz']


def test_the_class_key_covers_its_symbols():
    debt, declared, _ = gate.split_declared(
        _finding(['baz', 'qux']), {'acme/models/foo.py::Bar'})
    assert debt == []
    assert sorted(declared[0][4]) == ['baz', 'qux']


def test_the_file_key_covers_its_classes():
    debt, _, used = gate.split_declared(
        _finding(['baz']), {'acme/models/foo.py'})
    assert debt == []
    assert used == {'acme/models/foo.py'}


def test_an_entry_covering_nothing_stays_out_of_used():
    """De ahi salen las MUERTAS: declaradas menos usadas.

    Es el control que la poda del baseline de vocabulario enseño (H-DOCS-441):
    un registro que congela deuda inexistente miente sobre el arbol.
    """
    _, _, used = gate.split_declared(
        _finding(['baz']), {'acme/models/foo.py::Bar::ya-portado'})
    assert used == set()


def test_with_no_registry_nothing_is_declared():
    """Ante un archivo ausente el gate no absuelve: devuelve conjunto vacio."""
    original = gate.DECLARED_DIVERGENCES
    try:
        gate.DECLARED_DIVERGENCES = pathlib.Path('/no/existe/registro.txt')
        assert gate.load_divergences() == set()
    finally:
        gate.DECLARED_DIVERGENCES = original


@pytest.mark.parametrize('forbidden', ['write', 'save'])
def test_the_anti_abuse_clause_is_honoured_in_the_registry(forbidden):
    """`write` sale ausente 90 veces y NO se aliasa ni se declara divergencia.

    El docstring del gate lo descarta explicitamente: un alias convertiria
    noventa preguntas abiertas en noventa absoluciones silenciosas. Este caso
    vigila que nadie lo cuele por la puerta del registro.
    """
    for key in gate.load_divergences():
        assert not key.endswith(f'::{forbidden}'), (
            f'«{forbidden}» no puede declararse divergencia: es deuda contada')
