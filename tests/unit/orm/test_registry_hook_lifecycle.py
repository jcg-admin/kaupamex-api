"""El ciclo de vida de ``_register_hook``/``_unregister_hook`` en el registro.

La fuente los invoca en dos sitios. Al cargar, una sola vez y con el
registro todavía sin ``ready`` (``odoo19c: odoo/modules/loading.py:588-595``,
STEP 9). Y alrededor de ``_setup_models__`` cuando el registro ya está listo:
desinstala antes de rehacer el setup y reinstala después
(``odoo19c: odoo/orm/registry.py:396-399,498-503``); con ``ready`` falso no
toca los ganchos. En los dos casos los recibe un recordset vacío de cada
modelo (``env.values()``).

*Métrica:* la secuencia de llamadas a los dos ganchos, por modelo, y el valor
de ``ready`` en el momento de cada una.
El volcado que sigue a cada instalación (``env.flush_all()``,
``loading.py:595`` y ``registry.py:503``) se mide por su llamada.

*Ciega a:* lo que un gancho concreto escriba, que no existe todavía en este
árbol; y a los modelos de Django que no derivan de ``BaseModel``, que no
tienen ganchos.
"""
import pytest

from orm.environments import Environment
from orm.models import BaseModel
from orm.registry import Registry
from tests.conftest import preserved_registries

NAME = 'hooks'


@pytest.fixture
def calls(monkeypatch):
    """Registra cada llamada como ``(evento, modelo, vacío, ready)``."""
    seen = []

    def recorder(event):
        def hook(self):
            registry = Registry.registries.get(NAME)
            seen.append((event, type(self)._name, not self._ids,
                         registry.ready if registry else None))
        return hook

    monkeypatch.setattr(BaseModel, '_register_hook', recorder('register'))
    monkeypatch.setattr(BaseModel, '_unregister_hook',
                        recorder('unregister'))
    monkeypatch.setattr(Environment, 'flush_all',
                        lambda self: seen.append(('flush', None, True, None)))
    with preserved_registries():
        yield seen


def _hook_calls(calls):
    return [call for call in calls if call[0] != 'flush']


def _hooked(registry):
    return sorted(name for name, model in registry.models.items()
                  if isinstance(model, type) and issubclass(model, BaseModel))


def test_loading_registers_each_model_once_before_ready(calls):
    registry = Registry(NAME)
    assert registry.ready is True
    assert _hooked(registry)
    hooks = _hook_calls(calls)
    assert sorted(call[1] for call in hooks) == _hooked(registry)
    assert {call[0] for call in hooks} == {'register'}
    assert all(call[2] for call in hooks)
    assert {call[3] for call in hooks} == {False}
    # ``hooks`` no nombra ninguna conexión: el registro no tiene cursor ni
    # nada propio que volcar, y el entorno de quien lo pide no es suyo.
    assert 'flush' not in {call[0] for call in calls}


def test_setup_on_a_ready_registry_unregisters_then_registers(calls):
    registry = Registry(NAME)
    calls.clear()
    registry._setup_models__(None)
    names = _hooked(registry)
    assert [call[0] for call in calls] == (
        ['unregister'] * len(names) + ['register'] * len(names) + ['flush'])
    assert sorted(call[1] for call in calls if call[0] == 'register') == names
    assert sorted(call[1] for call in calls
                  if call[0] == 'unregister') == names


def test_setup_on_a_registry_being_loaded_leaves_the_hooks(calls):
    registry = Registry(NAME)
    calls.clear()
    registry.ready = False
    registry._setup_models__(None)
    assert calls == []
