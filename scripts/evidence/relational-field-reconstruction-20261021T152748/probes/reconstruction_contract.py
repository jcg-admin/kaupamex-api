"""Verificador acotado de 0419; opcionalmente restaura el helper anterior en memoria."""
import ast
import importlib
import os
import subprocess
import sys
import unittest

import django
from django.conf import settings


settings.configure(INSTALLED_APPS=['django.contrib.contenttypes'],
                   DEFAULT_AUTO_FIELD='django.db.models.AutoField')
django.setup()
importlib.import_module('orm.models')
if '--baseline' in sys.argv:
    os.environ['ORM_RECONSTRUCTION_BASELINE'] = '1'
    source = subprocess.check_output([
        'git', 'show', '79bc956e15f83c19714585246ba41501234a51fe:src/orm/fields.py'
    ], text=True)
    module = importlib.import_module('orm.fields')
    for name in ('_merge_field_definitions', '_m2m_contribute_to_class'):
        node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef)
                    and n.name == name)
        exec(compile(ast.Module(body=[node], type_ignores=[]), '<original relation>', 'exec'),
             module.__dict__)
    for field_type in (module.models.ForeignKey, module.models.ManyToManyField):
        if hasattr(field_type.__init__, '__wrapped__'):
            field_type.__init__ = field_type.__init__.__wrapped__
    module.models.ForeignKey.contribute_to_class = module._DJANGO_FK_CONTRIBUTE
    module.models.ManyToManyField.contribute_to_class = module._m2m_contribute_to_class
suite = unittest.defaultTestLoader.discover(
    'tests/unit/orm', pattern='test_relational_field_reconstruction.py')
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(not result.wasSuccessful())
