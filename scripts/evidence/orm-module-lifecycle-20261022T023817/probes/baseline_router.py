"""Control congelado: algoritmo y política del router en f04dfd1b."""
import ast
import importlib.util
from pathlib import Path
import subprocess
import tempfile

import django
django.setup()
import orm.routers
import pytest

revision = 'f04dfd1b9884998996bff8161f4962cea7f7fb7c'
source = subprocess.check_output(['git', 'show', revision + ':src/orm/routers.py'], text=True)
settings_source = subprocess.check_output(['git', 'show', revision + ':src/config/settings/base.py'], text=True)
policy = next(ast.literal_eval(n.value) for n in ast.parse(settings_source).body
              if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name)
                 and t.id == 'MULTIDB_CONTROL_PLANE_APPS' for t in n.targets))
with tempfile.TemporaryDirectory(prefix='router-baseline-') as temp:
    path = Path(temp) / 'baseline.py'
    path.write_text(source)
    spec = importlib.util.spec_from_file_location('baseline_router', path)
    baseline = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(baseline)
    baseline._CONTROL_PLANE_APPS = frozenset(policy)
    orm.routers.CompanyDatabaseRouter = baseline.CompanyDatabaseRouter
    print('Frozen baseline', revision, 'control-plane policy', policy, flush=True)
    raise SystemExit(pytest.main(['--confcutdir=tests/unit/orm', '-o', 'addopts=',
                                 '--tb=short', '-q', 'tests/unit/orm/test_router_database_contract.py']))
