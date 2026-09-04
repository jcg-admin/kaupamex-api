"""``Registry`` tramo 3 — carga, setup y la cola de restricciones.

Los seis simbolos que la referencia declara para poblar un registro y llevar
sus modelos a la base: ``load`` (``odoo19c: odoo/orm/registry.py:350``),
``_setup_models__`` (``:383``), ``post_init`` (``:686``), ``post_constraint``
(``:690``), ``finalize_constraints`` (``:711``) e ``init_models`` (``:723``).

Con ellos van las dos banderas de invalidacion —``registry_invalidated``
(``:1018``) y ``cache_invalidated`` (``:1027``)—, que no son tramo 3 sino 5:
entran aqui porque ``_setup_models__`` **escribe** la primera y sin ella el
metodo no se puede portar entero. Es dependencia medida, no adelanto.

**Los controles que discriminan:**

- ``test_a_failing_constraint_is_queued_not_raised`` — ``post_constraint``
  atrapa y encola; sin este caso, uno que dejara propagar la excepcion pasaria
  el camino feliz.
- ``test_the_flag_is_per_thread`` — las banderas viven en un
  ``threading.local``. Con un atributo de instancia normal el caso cae, y un
  hilo veria la invalidacion de otro.
- ``test_the_three_temporaries_are_gone_afterwards`` — ``init_models`` las
  borra en su ``finally``. Sin el caso, una fuga se quedaria como estado del
  registro entre llamadas.
"""
import logging
import threading

import pytest
from django.apps import apps
from django.db import connection

from addons.base.models.ir_module import IrModule
from orm.registry import Registry


@pytest.fixture
def registry(db):
    Registry.delete_all()
    built = Registry('default')
    yield built
    Registry.delete_all()


class TestTheInvalidationFlags:
    """≙ ``registry_invalidated`` (``:1018``) y ``cache_invalidated`` (``:1027``)."""

    def test_the_registry_flag_starts_false(self, registry):
        assert registry.registry_invalidated is False

    def test_setting_the_registry_flag_sticks(self, registry):
        registry.registry_invalidated = True
        assert registry.registry_invalidated is True

    def test_the_cache_flag_starts_empty(self, registry):
        assert registry.cache_invalidated == set()

    def test_the_cache_flag_is_the_same_set_on_every_read(self, registry):
        first = registry.cache_invalidated
        first.add('default')
        assert 'default' in registry.cache_invalidated

    def test_the_flag_is_per_thread(self, registry):
        """El control: la fuente las guarda en un ``threading.local``.

        Con un atributo de instancia normal, el hilo veria el ``True`` que el
        principal acaba de escribir — y una invalidacion se propagaria a quien
        no la hizo.
        """
        registry.registry_invalidated = True
        seen = []

        def read():
            seen.append(registry.registry_invalidated)

        thread = threading.Thread(target=read)
        thread.start()
        thread.join(timeout=5)
        assert seen == [False]


class TestPostInit:
    """≙ ``post_init`` (``:686-688``) — encola para el final de ``init_models``."""

    @pytest.fixture(autouse=True)
    def queue(self, registry):
        registry._post_init_queue = __import__('collections').deque()

    def test_it_queues_the_call(self, registry):
        registry.post_init(len, [1, 2, 3])
        assert len(registry._post_init_queue) == 1

    def test_the_arguments_travel_with_it(self, registry):
        seen = []
        registry.post_init(lambda *args, **kwargs: seen.append((args, kwargs)),
                           'alfa', key='beta')
        registry._post_init_queue.popleft()()
        assert seen == [(('alfa',), {'key': 'beta'})]

    def test_it_does_not_run_the_function(self, registry):
        """El control: encolar no es llamar."""
        seen = []
        registry.post_init(seen.append, 'alfa')
        assert seen == []


class TestPostConstraint:
    """≙ ``post_constraint`` (``:690-709``)."""

    @pytest.fixture(autouse=True)
    def install_mode(self, registry):
        registry._is_install = False
        registry._constraint_queue = {}

    def test_a_working_constraint_runs_now(self, registry, db):
        seen = []
        registry.post_constraint(None, lambda cr: seen.append('ran'), 'clave')
        assert seen == ['ran']
        assert registry._constraint_queue == {}

    def test_a_failing_constraint_is_queued_not_raised(self, registry, db, caplog):
        """El control: la fuente atrapa; dejar propagar rompe la instalacion."""
        caplog.set_level(logging.INFO, logger='kaupamex.schema')

        def boom(cr):
            raise RuntimeError('la restriccion no aplica todavia')

        registry.post_constraint(None, boom, 'clave')
        assert 'clave' in registry._constraint_queue

    def test_an_already_queued_key_is_only_replaced(self, registry, db):
        """La fuente no la vuelve a aplicar: ya esta marcada como pendiente."""
        seen = []
        registry._constraint_queue['clave'] = lambda cr: None
        registry.post_constraint(None, lambda cr: seen.append('ran'), 'clave')
        assert seen == []
        assert 'clave' in registry._constraint_queue

    def test_during_an_install_it_logs_error_and_does_not_queue(self, registry, db,
                                                               caplog):
        caplog.set_level(logging.ERROR, logger='kaupamex.schema')
        registry._is_install = True

        def boom(cr):
            raise RuntimeError('fallo de instalacion')

        registry.post_constraint(None, boom, 'clave')
        assert registry._constraint_queue == {}
        assert 'fallo de instalacion' in caplog.text


class TestFinalizeConstraints:
    """≙ ``finalize_constraints`` (``:711-721``)."""

    def test_it_runs_what_was_queued(self, registry, db):
        seen = []
        registry._constraint_queue = {'clave': lambda cr: seen.append('ran')}
        registry.finalize_constraints(None)
        assert seen == ['ran']

    def test_it_empties_the_queue(self, registry, db):
        registry._constraint_queue = {'clave': lambda cr: None}
        registry.finalize_constraints(None)
        assert registry._constraint_queue == {}

    def test_a_failure_only_warns(self, registry, db, caplog):
        """La fuente lo dice: *"this is not a deployment showstopper"*."""
        caplog.set_level(logging.WARNING, logger='kaupamex.schema')

        def boom(cr):
            raise RuntimeError('sigue sin aplicar')

        registry._constraint_queue = {'clave': boom}
        registry.finalize_constraints(None)
        assert 'sigue sin aplicar' in caplog.text
        assert registry._constraint_queue == {}


class TestLoad:
    """≙ ``load`` (``:350-380``) — los modelos que un modulo aporta."""

    def test_it_returns_the_names_of_the_module_models(self, registry):
        names = registry.load('base')
        assert 'res.partner' in names
        assert 'res.users' in names

    def test_an_unknown_module_yields_nothing(self, registry):
        """El control: sin esto, devolver todo el registro pasaria el positivo."""
        assert registry.load('no_existe_este_modulo') == []

    def test_it_accepts_the_node_shape_of_the_reference(self, registry):
        class _Node:
            name = 'base'

        assert 'res.partner' in registry.load(_Node())

    def test_it_clears_the_trigger_memo(self, registry):
        partner = apps.get_model('base', 'ResPartner')
        registry.get_field_trigger_tree(partner._meta.get_field('is_company'))
        assert registry._field_trigger_trees
        registry.load('base')
        assert registry._field_trigger_trees == {}


class TestSetupModels:
    """≙ ``_setup_models__`` (``:383-...``)."""

    def test_it_marks_the_registry_invalidated(self, registry):
        registry.registry_invalidated = False
        registry._setup_models__(None)
        assert registry.registry_invalidated is True

    def test_it_clears_the_trigger_memo(self, registry):
        partner = apps.get_model('base', 'ResPartner')
        registry.get_field_trigger_tree(partner._meta.get_field('is_company'))
        registry._setup_models__(None)
        assert registry._field_trigger_trees == {}

    def test_naming_models_narrows_to_their_descendants(self, registry):
        """Con nombres, la fuente hace un setup incremental."""
        registry._setup_models__(None, ['res.partner'])
        assert registry.registry_invalidated is True


class TestInitModels:
    """≙ ``init_models`` (``:723-777``).

    **Precondicion de la operacion, no andamiaje del caso:** ``init_models``
    corre al instalar un modulo, y su paso de reflejo registra cada objeto de
    tabla contra la fila de ``ir_module_module`` que lo declara
    (``odoo19c: ir_model.py:1953`` la resuelve con un subquery por nombre). En
    un arbol instalado esa fila ya existe porque el escaneo de modulos corre
    antes; la base de pruebas no pasa por ahi, asi que la siembra el fixture.
    Es la misma preparacion que usa ``test_ir_model_relation_reflect.py``.
    """

    @pytest.fixture(autouse=True)
    def installed_module(self, db):
        IrModule.objects.get_or_create(
            name='base', defaults={'shortdesc': 'base', 'state': 'installed'})

    @pytest.fixture
    def cursor(self, db):
        """Un cursor real: los tres pasos de esquema lo usan.

        ``init_models`` lo recibe de su llamador tambien en la fuente
        (``odoo19c: odoo/orm/registry.py:723``). Pasarle ``None`` mediria un
        recorrido que nunca llega a ``check_indexes``, que es justo el paso que
        el porte de esta tanda tenia sin ejercer.
        """
        with connection.cursor() as opened:
            yield opened

    def test_no_names_is_a_no_op(self, registry, db):
        registry.init_models(None, [], {})
        assert not hasattr(registry, '_post_init_queue')

    def test_the_three_temporaries_are_gone_afterwards(self, registry, cursor):
        """El control: la fuente las borra en su ``finally`` (``:775-777``).

        Son estado de UNA llamada. Si se quedaran, la siguiente heredaria la
        cola de la anterior y aplicaria dos veces lo mismo.
        """
        registry.init_models(cursor, ['res.partner'], {})
        assert not hasattr(registry, '_post_init_queue')
        assert not hasattr(registry, '_foreign_keys')
        assert not hasattr(registry, '_is_install')

    def test_it_drains_the_post_init_queue(self, registry, cursor, monkeypatch):
        """Lo encolado durante el reflejo se ejecuta antes de salir.

        El gancho entra por ``_reflect_all``, que es el paso donde la fuente
        deja que los modelos registren su trabajo diferido.
        """
        seen = []

        def enqueue(bound_registry, model_names, context):
            bound_registry.post_init(seen.append, 'ran')

        monkeypatch.setattr(Registry, '_reflect_all', enqueue)
        registry.init_models(cursor, ['res.partner'], {})
        assert seen == ['ran']

    def test_it_forgets_the_ordinary_tables(self, registry, cursor):
        """≙ ``self._ordinary_tables = None`` (``:757``): el schema pudo cambiar."""
        registry._ordinary_tables = {'lo_que_sea'}
        registry.init_models(cursor, ['res.partner'], {})
        assert registry._ordinary_tables != {'lo_que_sea'}
