"""Mide TASK-GEN-0060 contra el cuerpo de Field.column_type de Odoo.

Sólo compara la decisión de tipo PostgreSQL, no ejecuta migraciones ni abre
conexiones. El control sin translate debe coincidir; el caso traducible
devuelve exit 1 si conserva varchar donde la referencia exige jsonb.
"""
import ast
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import django
from django.conf import settings
from django.db import connection

API_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(API_ROOT / 'scripts'))
sys.path.insert(0, str(API_ROOT / 'src'))
from reference_roots import require  # noqa: E402

settings.configure(INSTALLED_APPS=['django.contrib.contenttypes'], USE_TZ=True,
                   DATABASES={'default': {'ENGINE': 'django.db.backends.postgresql'}})
django.setup()
import orm.models  # noqa: E402,F401
from orm.fields import Char  # noqa: E402


def main():
    source = require() / 'odoo/orm/fields.py'
    tree = ast.parse(source.read_text())
    field = next(node for node in tree.body
                 if isinstance(node, ast.ClassDef) and node.name == 'Field')
    method = next(node for node in field.body
                  if isinstance(node, ast.FunctionDef) and node.name == 'column_type')
    method.decorator_list = []
    namespace = {}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])),
                 str(source), 'exec'), namespace)
    reference_type = namespace['column_type']
    measurements = []
    for translated in (False, True):
        subject = SimpleNamespace(company_dependent=False, translate=translated,
                                  _column_type=('varchar', 'varchar'))
        expected = reference_type(subject)[0]
        actual = Char(max_length=24, translate=translated).db_type(connection)
        measurements.append({'translate': translated, 'reference': expected,
                             'consumer': actual,
                             'matches': actual.split('(', 1)[0] == expected})
    assert measurements[0]['matches'], 'El control sin traducción no coincide'
    assert connection.connection is None, 'La sonda no debe abrir conexiones'
    gap = not measurements[1]['matches']
    print(json.dumps({'task': 'TASK-GEN-0060', 'measurements': measurements,
                      'implementation_gap': gap, 'database_connections': 0}))
    return 1 if gap else 0


if __name__ == '__main__':
    raise SystemExit(main())
