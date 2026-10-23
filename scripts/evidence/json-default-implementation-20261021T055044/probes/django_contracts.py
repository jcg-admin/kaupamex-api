"""Verificador Consumer acotado, con control de anulación sólo en memoria."""
import ast
import importlib
import subprocess
import sys

import django
import pytest
from django.conf import settings


settings.configure(
    INSTALLED_APPS=['django.contrib.contenttypes'],
    DEFAULT_AUTO_FIELD='django.db.models.AutoField',
    DATABASES={'default': {'ENGINE': 'django.db.backends.postgresql',
                           'NAME': 'kaupamex_core_qa'}},
)
django.setup()
importlib.import_module('orm.models')
if '--baseline' in sys.argv:
    # Retira únicamente la corrección de Json, sin tocar el árbol de trabajo.
    source = subprocess.check_output([
        'git', 'show', '6d8c0afb37865681c5c98b9d553d72a5117143f2:src/orm/fields_misc.py'
    ], text=True)
    node = next(n for n in ast.parse(source).body
                if isinstance(n, ast.FunctionDef) and n.name == 'Json')
    module = importlib.import_module('orm.fields_misc')
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<baseline Json>', 'exec'),
         module.__dict__)
    if 'fields' in sys.modules:
        sys.modules['fields'].Json = module.Json
    print('Negative control: original Json factory restored in memory only')

raise SystemExit(pytest.main([
    '--confcutdir=tests/unit/orm', '-o', 'DJANGO_SETTINGS_MODULE=', '-o', 'addopts=',
    'tests/unit/orm/test_field_required_declared.py',
    'tests/unit/orm/test_declared_source_vocabulary.py',
    'tests/unit/orm/test_json_defaults.py', '-q',
]))
