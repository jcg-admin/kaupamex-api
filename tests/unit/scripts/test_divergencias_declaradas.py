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
POSITIVO = 'base_sparse_field/models/models.py::Base::_valid_field_parameter'


def test_el_registro_existe_y_no_esta_vacio():
    """Un registro ausente o vacio haria que todo el resto pase por vacuidad."""
    assert gate.DIVERGENCIAS.is_file()
    assert gate.cargar_divergencias(), (
        'registro vacio: los tests de abajo pasarian sin medir nada')


def test_el_positivo_real_esta_declarado():
    assert POSITIVO in gate.cargar_divergencias()


def test_los_comentarios_no_entran_como_entradas():
    """El `#` abre comentario, y la cabecera es casi todo el archivo."""
    for clave in gate.cargar_divergencias():
        assert not clave.startswith('#')
        assert clave


def test_cada_entrada_tiene_motivo_encima():
    """Una entrada sin motivo es una absolucion, no una declaracion.

    Se exige al menos un renglon de comentario NO vacio inmediatamente antes.
    """
    lineas = gate.DIVERGENCIAS.read_text(encoding='utf-8').splitlines()
    for i, linea in enumerate(lineas):
        if not linea.strip() or linea.lstrip().startswith('#'):
            continue
        previas = [l for l in lineas[:i][::-1]]
        anterior = next((l for l in previas if l.strip()), '')
        assert anterior.lstrip().startswith('#'), (
            f'la entrada «{linea.strip()}» no lleva motivo encima')


def test_las_tres_granularidades_de_clave():
    claves = gate.claves_de('acme', 'foo.py', 'Bar', 'baz')
    assert claves == (
        'acme/models/foo.py::Bar::baz',
        'acme/models/foo.py::Bar',
        'acme/models/foo.py',
    )


def _hallazgo(simbolos):
    return [('acme', 'foo.py', 'Bar', 'MÉTODOS AUSENTES', list(simbolos))]


def test_lo_declarado_sale_de_la_deuda_y_entra_en_su_propio_conteo():
    deuda, declarados, usadas = gate.separar_declarado(
        _hallazgo(['baz']), {'acme/models/foo.py::Bar::baz'})
    assert deuda == []
    assert declarados[0][4] == ['baz']
    assert usadas == {'acme/models/foo.py::Bar::baz'}


def test_una_entrada_de_simbolo_NO_absuelve_la_clase_entera():
    """El criterio de `CLASE EXTENDIDA`: nunca se absuelve de mas."""
    deuda, declarados, _ = gate.separar_declarado(
        _hallazgo(['baz', 'qux']), {'acme/models/foo.py::Bar::baz'})
    assert deuda[0][4] == ['qux'], 'el pendiente tiene que sobrevivir'
    assert declarados[0][4] == ['baz']


def test_la_clave_de_clase_cubre_sus_simbolos():
    deuda, declarados, _ = gate.separar_declarado(
        _hallazgo(['baz', 'qux']), {'acme/models/foo.py::Bar'})
    assert deuda == []
    assert sorted(declarados[0][4]) == ['baz', 'qux']


def test_la_clave_de_archivo_cubre_sus_clases():
    deuda, _, usadas = gate.separar_declarado(
        _hallazgo(['baz']), {'acme/models/foo.py'})
    assert deuda == []
    assert usadas == {'acme/models/foo.py'}


def test_una_entrada_que_no_cubre_nada_queda_fuera_de_usadas():
    """De ahi salen las MUERTAS: declaradas menos usadas.

    Es el control que la poda del baseline de vocabulario enseño (H-DOCS-441):
    un registro que congela deuda inexistente miente sobre el arbol.
    """
    _, _, usadas = gate.separar_declarado(
        _hallazgo(['baz']), {'acme/models/foo.py::Bar::ya-portado'})
    assert usadas == set()


def test_sin_registro_no_se_declara_nada():
    """Ante un archivo ausente el gate no absuelve: devuelve conjunto vacio."""
    original = gate.DIVERGENCIAS
    try:
        gate.DIVERGENCIAS = pathlib.Path('/no/existe/registro.txt')
        assert gate.cargar_divergencias() == set()
    finally:
        gate.DIVERGENCIAS = original


@pytest.mark.parametrize('prohibido', ['write', 'save'])
def test_la_clausula_anti_abuso_se_respeta_en_el_registro(prohibido):
    """`write` sale ausente 90 veces y NO se aliasa ni se declara divergencia.

    El docstring del gate lo descarta explicitamente: un alias convertiria
    noventa preguntas abiertas en noventa absoluciones silenciosas. Este caso
    vigila que nadie lo cuele por la puerta del registro.
    """
    for clave in gate.cargar_divergencias():
        assert not clave.endswith(f'::{prohibido}'), (
            f'«{prohibido}» no puede declararse divergencia: es deuda contada')
