"""El gate de porte reconoce la extensión cross-app (H-API-557, tarea #316).

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
import importlib.util
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
    mapa, no_resolubles = gate.instalaciones_del_addon(raiz)
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
    assert gate._clase_sin_contraparte(
        'x', 'f.py', 'Cualquiera', {'a', 'b'}, {}) == (
            'x', 'f.py', 'Cualquiera', 'CLASE AUSENTE', ['a', 'b'])


def test_an_extended_class_reports_only_what_is_pending():
    """Nunca absuelve: lo instalado se descuenta, el resto se lista."""
    assert gate._clase_sin_contraparte(
        'x', 'f.py', 'C', {'uno', 'dos', 'tres'}, {'C': {'uno'}}) == (
            'x', 'f.py', 'C', 'CLASE EXTENDIDA', ['dos', 'tres'])


def test_a_fully_covered_extension_is_not_a_finding():
    """Una extensión de sólo campos cubre entera una clase sin métodos."""
    assert gate._clase_sin_contraparte(
        'x', 'f.py', 'C', set(), {'C': {'campo'}}) is None
    assert gate._clase_sin_contraparte(
        'x', 'f.py', 'C', {'uno'}, {'C': {'uno'}}) is None


def test_write_is_not_aliased_to_save():
    """Decisión declarada: el alias absolvería 90 preguntas de golpe.

    Ver la sección homónima del docstring del gate — es la amplitud que #164
    ya quitó por fabricar coincidencias.
    """
    assert gate.normaliza('write') != gate.normaliza('save')
    assert 'write' not in gate.PORTE_ALIAS
