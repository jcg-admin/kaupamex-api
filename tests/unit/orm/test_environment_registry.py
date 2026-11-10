"""``env.registry`` es el ``Registry`` de la base del entorno.

≙ ``odoo19c: odoo/orm/environments.py:172`` (``env.registry``) y
``odoo/orm/registry.py:84,309-320`` (``class Registry(Mapping[str,
type[BaseModel]])``): quien necesita la **clase** de un modelo la pide al
registro (``env.registry[name]``, ``self.pool[name]``), no a ``env[name]``,
que en la fuente es un recordset. Diseño:
``designs/environment-getitem-recordset.md`` (G1, TASK-API-0485).
"""
import pytest

from orm import registry as registry_module
from orm.environments import Environment
from orm.registry import Registry
from orm.utils import SUPERUSER_ID

pytestmark = pytest.mark.django_db


@pytest.fixture
def env(db):
    with Environment(None, SUPERUSER_ID, {}) as environment:
        yield environment


def test_env_registry_is_the_registry_of_its_database(env):
    assert isinstance(env.registry, Registry)
    assert env.registry is Registry(env.db_alias)


def test_env_registry_maps_names_to_model_classes(env):
    model = env.registry['test_orm.shared.compute']
    assert isinstance(model, type)
    assert model._name == 'test_orm.shared.compute'
    assert 'test_orm.shared.compute' in env.registry
    assert set(env.registry) == set(registry_module.MODELS_BY_NAME)


def test_env_registry_rejects_an_unknown_model(env):
    with pytest.raises(KeyError):
        env.registry['test_orm.no.such.model']


def test_env_registry_clears_caches_like_the_reference(env, monkeypatch):
    """``Registry.clear_cache(*cache_names)`` (``registry.py:971-987``) es
    método de la instancia; aquí delega en el eje de proceso del módulo."""
    assert 'clear_cache' in vars(Registry)
    seen = []
    monkeypatch.setattr(registry_module, 'clear_cache',
                        lambda *names: seen.append(names))
    env.registry.clear_cache('default', 'stable')
    assert seen == [('default', 'stable')]
