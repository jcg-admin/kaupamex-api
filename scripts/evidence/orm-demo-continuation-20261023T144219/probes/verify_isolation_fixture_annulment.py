"""Anula sólo el guard de recursos existentes en una copia en memoria."""
import pytest


class AnnulExistingResourceGuard:
    @pytest.hookimpl(hookwrapper=True)
    def pytest_fixture_setup(self, fixturedef, request):
        outcome = yield
        if fixturedef.argname == 'isolation_module':
            module = outcome.get_result()
            source = open(module.__file__, encoding='utf-8').read()
            guard = 'if alias in settings.DATABASES or svc.database_exists(alias):'
            assert source.count(guard) == 1
            exec(compile(source.replace(guard, 'if False:'), module.__file__, 'exec'), module.__dict__)


raise SystemExit(pytest.main([
    'tests/unit/service/test_isolation_fixture_safety.py',
    '--confcutdir=tests/unit/service', '-q', '-o', 'addopts=',
], plugins=[AnnulExistingResourceGuard()]))
