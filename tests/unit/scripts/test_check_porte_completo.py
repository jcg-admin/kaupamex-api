"""El gate de porte reconoce la extensión cross-app (H-API-569, tarea #316).

Estos tests son **puros**: no tocan Django ni la base. Miden el instrumento,
no el código de aplicación — y existen porque :ref:`h-api-556` dejó dicho que
los gates de este árbol fallan por su instrumento, no por su idea, y que la
prueba que sirve es contra un **positivo conocido del repo**, no contra un
caso fabricado por quien escribió el patrón.

El positivo conocido es ``base_sparse_field``: instala cuatro símbolos sobre
``base.IrModelFields`` desde ``ready()``, y antes de #316 el gate los
reportaba como clase ausente.
"""
import ast
import contextlib
import importlib.util
import io
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    'check_porte_completo', REPO / 'scripts' / 'check_porte_completo.py')
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)


def _llamada(codigo):
    """El primer ``ast.Call`` de un fragmento."""
    return next(n for n in ast.walk(ast.parse(codigo)) if isinstance(n, ast.Call))


# --- las tres formas de instalación que el árbol usa hoy -------------------


@pytest.mark.parametrize('codigo, esperado', [
    ("chain_method(IrModelFields, 'save', guardia)", ('IrModelFields', 'save')),
    ("ResBank.add_to_class('l10n_mx_edi_code', campo)",
     ('ResBank', 'l10n_mx_edi_code')),
    ("_add_if_absent(ResCompany, 'chart_template', campo)",
     ('ResCompany', 'chart_template')),
])
def test_the_three_installation_forms_are_read(codigo, esperado):
    assert gate._destino_y_clave(_llamada(codigo)) == esperado


def test_a_call_that_is_not_an_installation_is_ignored():
    assert gate._destino_y_clave(_llamada('foo(Bar, "x")')) == (None, None)


def test_a_non_literal_symbol_name_is_ignored():
    """Sin cadena constante no hay nombre que atribuir — el lado seguro."""
    assert gate._destino_y_clave(
        _llamada('chain_method(C, nombre, f)')) == (None, None)


def test_a_variable_receiver_yields_no_class():
    """``_add_if_absent(model, …)`` dentro de un bucle: el AST ve la variable."""
    destino, clave = gate._destino_y_clave(
        _llamada("_add_if_absent(model, 'is_published', campo)"))
    assert destino == 'model'
    assert destino in gate._RECEPTOR_NO_RESOLUBLE
    assert clave == 'is_published'


# --- el positivo conocido del repo ----------------------------------------


def test_the_real_addon_declares_its_installations():
    """``base_sparse_field`` cuelga cuatro símbolos sobre ``IrModelFields``.

    Resuelve la ruta con ``addon_path``, no con una constante de raíz: desde el
    movimiento a dos raíces (:ref:`h-api-558`) ``base_sparse_field`` vive en
    ``<repo>/addons`` y ``base`` en ``src/addons``. Un test que fijara una de
    las dos volvería a romperse en cuanto un addon cambie de raíz — que es
    justo lo que pasó con la constante ``SRC`` que este test usaba.
    """
    raiz = gate.addon_path('base_sparse_field')
    assert raiz is not None, 'base_sparse_field no se resuelve en ninguna raíz'
    mapa, no_resolubles = gate.addon_installations(raiz)
    assert mapa[gate.normaliza('IrModelFields')] == {
        'reflect_fields', 'save', 'serialization_field_id', 'ttype_for'}
    assert no_resolubles == 0


def test_the_underscore_of_the_reference_normalizes_away():
    """``_reflect_fields`` de la referencia casa con nuestro ``reflect_fields``.

    Es la resolución concreta que la tarea #314 necesitaba: sin ella el gate
    seguiría reportando ausente un método portado.
    """
    assert gate.normaliza('_reflect_fields') == gate.normaliza('reflect_fields')


# --- el veredicto por clase ------------------------------------------------


def test_a_class_nobody_extends_is_absent():
    """``(hallazgo, absoluciones)`` — el segundo valor es el contador que
    ``compara()`` acumula para el denominador ``compute absueltos`` del
    reporte (H-API-612, ``api@d8a5fc4``). Sin ``absueltos`` en la llamada no
    hay nada que absolver, así que el contador es 0 — no el hallazgo solo.
    """
    assert gate._class_without_counterpart(
        'x', 'f.py', 'Cualquiera', {'a', 'b'}, {}) == (
            ('x', 'f.py', 'Cualquiera', 'CLASE AUSENTE', ['a', 'b']), 0)


def test_an_extended_class_reports_only_what_is_pending():
    """Nunca absuelve: lo instalado se descuenta, el resto se lista."""
    assert gate._class_without_counterpart(
        'x', 'f.py', 'C', {'uno', 'dos', 'tres'}, {'C': {'uno'}}) == (
            ('x', 'f.py', 'C', 'CLASE EXTENDIDA', ['dos', 'tres']), 0)


def test_a_fully_covered_extension_is_not_a_finding():
    """Una extensión de sólo campos cubre entera una clase sin métodos."""
    assert gate._class_without_counterpart(
        'x', 'f.py', 'C', set(), {'C': {'campo'}}) == (None, 0)
    assert gate._class_without_counterpart(
        'x', 'f.py', 'C', {'uno'}, {'C': {'uno'}}) == (None, 0)


def test_absolved_symbols_are_counted_in_the_second_value():
    """El contador SÍ sube cuando ``absueltos`` cubre un símbolo pendiente.

    Sin este caso los tres tests de arriba nunca ejercitan el parámetro
    ``absueltos``, y el contador siempre da 0 — no alcanza para distinguir
    "el contador existe y funciona" de "el contador siempre es cero".
    """
    finding, absolutions = gate._class_without_counterpart(
        'x', 'f.py', 'C', {'uno', 'dos'}, {}, absueltos={'uno'})
    assert finding == ('x', 'f.py', 'C', 'CLASE AUSENTE', ['dos'])
    assert absolutions == 1


def test_write_is_not_aliased_to_save():
    """Decisión declarada: el alias absolvería 90 preguntas de golpe.

    Ver la sección homónima del docstring del gate — es la amplitud que #164
    ya quitó por fabricar coincidencias.
    """
    assert gate.normaliza('write') != gate.normaliza('save')
    assert 'write' not in gate.PORTE_ALIAS


# --- el informe de entradas muertas declara su denominador (H-API-849) -----
#
# El positivo conocido del repo: `--addon base` reportaba **70 MUERTAS**,
# todas de `authz_*`, y dos de las tres verificadas a mano seguían siendo
# divergencias legítimas con su símbolo ausente. Sin `--addon`, 248 de 248
# vivas. Actuar sobre ese informe habría retirado setenta declaraciones
# válidas en silencio.


def _correr(*argv):
    """Corre el gate capturando su salida, sin tocar el proceso."""
    salida = io.StringIO()
    with contextlib.redirect_stdout(salida):
        gate.main(list(argv))
    return salida.getvalue()


def test_a_scoped_run_names_no_entry_as_dead():
    """El recorrido acotado no puede saber qué entrada está muerta.

    Lo que se mide es que **no nombre ninguna clave del registro**, no que la
    palabra falte: el propio mensaje explica por qué no las calcula, y buscar
    la palabra confundiría la explicación con el defecto. Lo que se consumiría
    al actuar sobre el informe es la lista, y ésa es la que no debe existir.

    Qué haría fallar a este control: devolver el cálculo global al recorrido
    acotado. Entonces la línea nombra entradas de otros addons y el caso cae.
    """
    salida = _correr('--addon', 'base')
    registro = [l for l in salida.splitlines()
                if l.startswith('divergencias declaradas:')]
    assert len(registro) == 1, salida
    claves = gate.load_divergences()
    assert claves, 'el registro está vacío: el caso no mediría nada'
    nombradas = [clave for clave in claves if clave in registro[0]]
    assert nombradas == [], nombradas


def test_a_scoped_run_names_the_scope_of_its_count():
    """El conteo no se calla el alcance: lo dice en la misma línea.

    Sin esto, `178 de 248 entrada(s) vivas` se lee como setenta muertas — que
    es exactamente el defecto, con o sin la lista.
    """
    salida = _correr('--addon', 'base')
    registro = next(l for l in salida.splitlines()
                    if l.startswith('divergencias declaradas:'))
    assert 'tocadas por el recorrido' in registro, registro
    assert '--addon base' in registro, registro
    assert 'de 248 entrada(s) vivas' not in registro, registro
