"""Comprueba admisión real de modelos Django con manifests controlados."""
import ast
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest import mock

# El proceso tiene settings propios; no cambia el entorno de la aplicación.
os.environ.pop('DJANGO_SETTINGS_MODULE', None)
sys.path.insert(0, str(Path.cwd() / 'scripts'))
from counterpart_body import declarations_of
import django
from django.apps import apps
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from modules import module
from modules.module_graph import ModuleGraph

with TemporaryDirectory(prefix='startup-installability-') as directory:
    fixture_root = Path(directory)
    addon_root = fixture_root / 'addons'
    addon_root.mkdir()
    (addon_root / '__init__.py').write_text('')
    (fixture_root / 'core').mkdir()
    (fixture_root / 'core/__init__.py').write_text('')
    marker = fixture_root / 'disabled-imported'
    manifests = {
        'base': {'depends': []},
        'enabled': {'depends': ['base'], 'installable': True},
        'disabled': {'depends': ['base'], 'installable': False},
        'dependent': {'depends': ['disabled']},
    }
    for name, values in manifests.items():
        folder = addon_root / name
        folder.mkdir()
        (folder / '__init__.py').write_text('')
        (folder / '__manifest__.py').write_text(repr(dict(
            name='Controlled fixture', license='LGPL-3', **values)))
        if name in ('disabled', 'dependent'):
            model_source = ('from pathlib import Path\n'
                            'Path(%r).write_text("imported")\n'
                            'raise RuntimeError("Disabled addon code imported")\n') % str(marker)
        else:
            model_source = ('from django.db import models\n'
                            'class StartupProbe(models.Model):\n'
                            '    value = models.CharField(max_length=20)\n')
        (folder / 'models.py').write_text(model_source)
    source = Path('src/config/settings/base.py')
    if '--annul' in sys.argv:
        source = fixture_root / 'base-before.py'
        source.write_bytes(subprocess.check_output([
            'git', 'show', '3fb301a542c218981aed5eb8274003083671c0b5:src/config/settings/base.py']))
    declaration = next(row for row in declarations_of(source)
                       if row.kind == 'function' and row.name == '_local_apps')
    namespace = {'ModuleGraph': ModuleGraph, 'get_modules': module.get_modules,
                 'ImproperlyConfigured': ImproperlyConfigured}
    exec(compile(ast.Module(body=[declaration.node], type_ignores=[]),
                 str(source), 'exec'), namespace)
    with mock.patch.object(module, 'ADDONS_PATHS', (addon_root,)):
        selected = namespace['_local_apps']()
    # Los paquetes son fixtures de este proceso aislado, no los addons productivos.
    for name in ('addons', 'core'):
        sys.modules.pop(name, None)
    sys.path.insert(0, str(fixture_root))
    importlib.invalidate_caches()
    settings.configure(SECRET_KEY='isolated-startup-fixture', INSTALLED_APPS=selected,
                       DATABASES={'default': {'ENGINE': 'django.db.backends.postgresql',
                                              'NAME': 'unused_no_connection'}},
                       DEFAULT_AUTO_FIELD='django.db.models.BigAutoField')
    django.setup()
    assert apps.get_model('base', 'StartupProbe') is not None
    assert apps.get_model('enabled', 'StartupProbe') is not None
    assert not apps.is_installed('addons.disabled')
    assert not apps.is_installed('addons.dependent')
    assert not marker.exists()
    print(json.dumps({'result': 'PASS', 'selected': selected,
                      'registered_models': [model._meta.label for model in apps.get_models()],
                      'disabled_code_imported': marker.exists(),
                      'scope': 'Native Django startup, controlled packages/manifests and actual selector body; no SQL, SQLite or whole per-base Registry acceptance'}))
