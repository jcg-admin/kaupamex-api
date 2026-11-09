"""La forma de ``tools.sql`` contra ``odoo19c: odoo/tools/sql.py``.

La referencia se lee **por AST**: no se ejecuta ni se importa. De ella salen
``__all__``, ``SQL.__slots__``, la firma de ``SQL.__init__``, las anotaciones
de clase de ``SQL`` y la tabla de ``SQL_ORDER_BY_TYPE`` con su valor por
defecto. La prueba no lleva ninguna lista propia de esos valores. Diseño en
``designs/tools-sql-full-port.md`` del Workbench.

*Métrica:* los valores literales de la referencia frente a los atributos del
módulo cargado.
*Ciega a:* el comportamiento de cada función, que miden ``test_sql.py`` y las
pruebas de sus consumidores.
"""
import ast
import inspect
import pathlib

import pytest

from tests.fixtures.reference_tree import reference_root
from tools import sql as ported

pytestmark = [pytest.mark.unit, pytest.mark.reference]


@pytest.fixture(scope='module')
def reference():
    path = pathlib.Path(reference_root()) / 'odoo' / 'tools' / 'sql.py'
    return ast.parse(path.read_text())


def _module_value(tree, name):
    for node in tree.body:
        targets = getattr(node, 'targets', ())
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == name for t in targets):
            return node.value
    raise LookupError(name)


def _sql_class(tree):
    return next(node for node in tree.body
                if isinstance(node, ast.ClassDef) and node.name == 'SQL')


def test_all_matches_the_reference(reference):
    expected = ast.literal_eval(_module_value(reference, '__all__'))
    assert ported.__all__ == expected


def test_sql_slots_match_the_reference(reference):
    slots = next(node.value for node in _sql_class(reference).body
                 if isinstance(node, ast.Assign)
                 and node.targets[0].id == '__slots__')
    assert ported.SQL.__slots__ == ast.literal_eval(slots)


def test_sql_init_signature_matches_the_reference(reference):
    init = next(node for node in _sql_class(reference).body
                if isinstance(node, ast.FunctionDef)
                and node.name == '__init__')
    expected = (
        [(a.arg, 'POSITIONAL_ONLY') for a in init.args.posonlyargs]
        + [(init.args.vararg.arg, 'VAR_POSITIONAL')]
        + [(a.arg, 'KEYWORD_ONLY') for a in init.args.kwonlyargs]
        + [(init.args.kwarg.arg, 'VAR_KEYWORD')]
    )
    params = inspect.signature(ported.SQL.__init__).parameters
    assert [(p.name, p.kind.name) for p in params.values()] == expected
    assert [params[a.arg].default for a in init.args.kwonlyargs] == [
        ast.literal_eval(d) for d in init.args.kw_defaults]


def test_sql_class_annotations_match_the_reference(reference):
    names = [node.target.id for node in _sql_class(reference).body
             if isinstance(node, ast.AnnAssign)]
    # Python transforma el nombre privado de clase (``__code`` →
    # ``_SQL__code``) al crear la clase, igual en la referencia que aquí.
    mangled = [f'_SQL{name}'
               if name.startswith('__') and not name.endswith('__')
               else name for name in names]
    assert list(ported.SQL.__annotations__) == mangled


def test_order_by_type_matches_the_reference_with_its_default(reference):
    call = _module_value(reference, 'SQL_ORDER_BY_TYPE')
    default = ast.literal_eval(call.args[0].body)
    table = ast.literal_eval(call.args[1])
    assert dict(ported.SQL_ORDER_BY_TYPE) == table
    assert ported.SQL_ORDER_BY_TYPE['no_such_type'] == default
