"""Contrasta resolve_mro con su cuerpo de referencia, sin importar Odoo.

Requiere ODOO19C mediante reference_roots. Ejecuta el código API real con
un registro Django mínimo y backend PostgreSQL, sin abrir conexiones. Mide
la cadena contigua de atributos, ausencia, None y precedencia de herencia;
no mide registro de addons, persistencia ni completitud de BaseModel.
La mutación break -> continue sólo existe en memoria y debe ser detectada.
"""
import ast
import json
import pathlib
import sys
from types import SimpleNamespace

import django
from django.conf import settings
from django.db import connections

API_ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(API_ROOT / 'scripts'))
sys.path.insert(0, str(API_ROOT / 'src'))
from reference_roots import require  # noqa: E402

settings.configure(INSTALLED_APPS=['django.contrib.contenttypes'], USE_TZ=True,
                   DATABASES={'default': {'ENGINE': 'django.db.backends.postgresql'}})
django.setup()
# El orden forma parte de la precondición medida del ORM actual.
import orm.models  # noqa: E402,F401
from orm.fields import resolve_mro  # noqa: E402


def compile_function(node, namespace):
    """Aísla una función; las anotaciones de Odoo no requieren sus imports."""
    prefix = ast.ImportFrom(module='__future__',
                            names=[ast.alias(name='annotations')], level=0)
    tree = ast.fix_missing_locations(ast.Module(body=[prefix, node], type_ignores=[]))
    exec(compile(tree, '<resolve-mro-probe>', 'exec'), namespace)
    return namespace['resolve_mro']


def main():
    reference = require() / 'odoo/orm/fields.py'
    source = ast.parse(reference.read_text())
    node = next(n for n in source.body
                if isinstance(n, ast.FunctionDef) and n.name == 'resolve_mro')
    original = compile_function(node, {'SENTINEL': object()})

    class Base:
        number = 1
        nothing = None
        tag = 'base'

    class Middle(Base):
        number = 'stop'
        tag = 'middle'

    class Leaf(Middle):
        number = 3
        nothing = None
        tag = 'leaf'

    cases = [('tag', lambda value: True, ['leaf', 'middle', 'base']),
             ('number', lambda value: isinstance(value, int), [3]),
             ('nothing', lambda value: value is None, [None, None]),
             ('absent', lambda value: True, []),
             ('__init__', lambda value: True, [])]
    adapter = SimpleNamespace(_model_classes__=Leaf.__mro__[:-1])
    for name, predicate, expected in cases:
        assert original(adapter, name, predicate) == expected, name
        assert resolve_mro(Leaf, name, predicate) == expected, name
        assert resolve_mro(Leaf(), name, predicate) == expected, name

    actual = ast.parse((API_ROOT / 'src/orm/fields.py').read_text())
    mutant = next(n for n in actual.body
                  if isinstance(n, ast.FunctionDef) and n.name == 'resolve_mro')
    breaks = [n for n in ast.walk(mutant) if isinstance(n, ast.Break)]
    assert len(breaks) == 1, 'La mutación debe tener un único objetivo'
    for parent in ast.walk(mutant):
        for _, value in ast.iter_fields(parent):
            if isinstance(value, list):
                for index, child in enumerate(value):
                    if child is breaks[0]:
                        value[index] = ast.Continue()
    altered = compile_function(mutant, dict(resolve_mro.__globals__))
    observed = altered(Leaf, 'number', lambda value: isinstance(value, int))
    assert observed == [3, 1] and observed != [3], 'El control no discriminó'
    assert all(conn.connection is None for conn in connections.all())
    print(json.dumps({'behavior': 'resolve_mro', 'reference_cases': len(cases),
                      'api_cases': len(cases) * 2, 'result': 'PASS',
                      'mutation': 'break -> continue', 'mutation_detected': True,
                      'source_files_modified': False, 'database_connections': 0}))


if __name__ == '__main__':
    main()
