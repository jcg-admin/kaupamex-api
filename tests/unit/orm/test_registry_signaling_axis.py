"""``Registry`` tramo 5 — la senalizacion entre procesos y el cursor.

Los siete simbolos que la referencia declara entre ``setup_signaling``
(``odoo19c: odoo/orm/registry.py:1036``) y ``cursor`` (``:1165``):
``setup_signaling``, ``get_sequences`` (``:1066``), ``check_signaling``
(``:1076``), ``signal_changes`` (``:1110``), ``reset_changes`` (``:1142``),
``manage_changes`` (``:1155``) y ``cursor``.

**Para que existe el eje.** La fuente guarda una secuencia por cache en tablas
``orm_signaling_<nombre>``: ``signal_changes`` la incrementa cuando un proceso
invalida, y ``check_signaling`` la lee al abrir cada peticion para enterarse de
lo que invalido **otro** proceso. Con ``workers = 4``
(``setup/gunicorn.conf.py:93``), sin ese eje una invalidacion local deja a los
otros tres sirviendo contenido viejo — la mitad que :ref:`h-api-980` declaro
ausente y que la tarea **#256** cierra.

**Los controles que discriminan:**

- ``test_the_module_invalidator_writes_what_the_signal_reads`` — es el caso que
  cae si las dos estructuras de cache vuelven a separarse. Antes de este tramo
  ``clear_cache`` escribia un conjunto de modulo que nadie leia, y la property
  ``cache_invalidated`` leia un ``threading.local`` que nadie escribia: el eje
  se habria portado entero y habria senalizado siempre cero.
- ``test_a_second_reader_sees_the_bump`` — dos lecturas de la secuencia con una
  senal en medio. Sin el, un ``signal_changes`` que no escribiera en la base
  pasaria igual, porque el emisor incrementa su propio contador en memoria.
- ``test_the_flag_is_per_thread`` (en el tramo 3) sigue siendo el control de
  que la anotacion no se propaga a un hilo que no la hizo.
"""
import threading
import warnings

import pytest
from django.db import connection

from orm.registry import (Registry, cache_of, clear_all_caches, clear_cache,
                          signaling_table_names)


@pytest.fixture
def registry(db):
    Registry.delete_all()
    built = Registry('default')
    built.cache_invalidated.clear()
    built.registry_invalidated = False
    yield built
    built.cache_invalidated.clear()
    built.registry_invalidated = False
    Registry.delete_all()


@pytest.fixture
def cursor(db):
    with connection.cursor() as opened:
        yield opened


class TestTheSignalingTables:
    """La migracion crea las siete tablas que el eje lee y escribe."""

    def test_it_names_one_table_per_cache_key_plus_the_registry(self):
        names = signaling_table_names()
        assert names[0] == 'orm_signaling_registry'
        assert 'orm_signaling_groups' in names
        assert len(names) == 7

    def test_every_table_exists_in_the_schema(self, cursor):
        """El control: sin la migracion, este caso cae y nombra la que falta."""
        cursor.execute(
            "SELECT table_name FROM information_schema.tables"
            " WHERE table_name = ANY(%s) AND table_schema = current_schema",
            [list(signaling_table_names())])
        found = {row[0] for row in cursor.fetchall()}
        assert found == set(signaling_table_names())


class TestGetSequences:
    """≙ ``get_sequences`` (``:1066-1074``)."""

    def test_it_returns_the_registry_sequence_and_one_per_cache(self, registry,
                                                                cursor):
        registry_sequence, cache_sequences = registry.get_sequences(cursor)
        assert isinstance(registry_sequence, int)
        assert set(cache_sequences) == {'default', 'assets', 'stable',
                                        'templates', 'routing', 'groups'}

    def test_every_sequence_starts_seeded(self, registry, cursor):
        """La fuente inserta una fila al crear la tabla, para que ``max(id)``
        no sea ``NULL`` (``:1056``). Sin la siembra, la primera comparacion de
        ``check_signaling`` compararia contra ``None``.
        """
        registry.setup_signaling()
        registry_sequence, cache_sequences = registry.get_sequences(cursor)
        assert registry_sequence >= 1
        assert all(value >= 1 for value in cache_sequences.values())


class TestSetupSignaling:
    """≙ ``setup_signaling`` (``:1036-1064``)."""

    def test_it_loads_the_sequences_into_the_registry(self, registry):
        assert registry.registry_sequence == -1
        registry.setup_signaling()
        assert registry.registry_sequence >= 1
        assert len(registry.cache_sequences) == 6

    def test_a_missing_table_is_named_not_created(self, registry, monkeypatch):
        """Divergencia de mecanismo declarada: aqui el DDL lo emiten las
        migraciones, asi que el metodo **avisa** en vez de crear — el mismo
        desenlace que ``check_tables_exist`` (:ref:`h-api-1057`).
        """
        monkeypatch.setattr('orm.registry.signaling_table_names',
                            lambda: ('orm_signaling_no_existe',))
        with pytest.raises(RuntimeError, match='orm_signaling_no_existe'):
            registry.setup_signaling()


class TestSignalChanges:
    """≙ ``signal_changes`` (``:1110-1140``)."""

    def test_it_does_nothing_when_nothing_was_invalidated(self, registry,
                                                          cursor):
        registry.ready = True
        registry.setup_signaling()
        before = registry.get_sequences(cursor)
        registry.signal_changes()
        assert registry.get_sequences(cursor) == before

    def test_a_second_reader_sees_the_bump(self, registry, cursor):
        """El control: la senal tiene que llegar a la BASE, no solo al contador
        en memoria del emisor. Este caso lee con un cursor ajeno al metodo.

        **Se afirma desigualdad, no ``+ 1``** — y no es una relajacion del
        control: es la propiedad que el mecanismo garantiza. La secuencia es
        ``max(id)`` de una tabla ``SERIAL``, y un ``INSERT`` revertido **quema
        el valor igual**: tras un caso que siembra y hace rollback, el
        siguiente ``INSERT`` aterriza en un id muy por encima del maximo
        sobreviviente. Medido: ``assert 95 == (1 + 1)`` al correr este archivo
        despues de ``tests/unit/base/test_ir_autovacuum_gc_signaling.py``.

        Es tambien lo unico que la fuente consume: ``check_signaling`` compara
        con ``!=`` (``:1096``), nunca con aritmetica.

        *Metrica:* ``max(id)`` de ``orm_signaling_groups`` antes y despues de
        una senal, leido por un cursor que no es el del emisor.
        *Ciega a:* cuantas filas se insertaron — un ``signal_changes`` que
        escribiera dos veces la misma cache pasaria igual. Lo que discrimina es
        que un emisor que no escriba en la base deja ``after == before``.
        """
        registry.ready = True
        registry.setup_signaling()
        _, before = registry.get_sequences(cursor)
        clear_cache('groups')
        registry.signal_changes()
        _, after = registry.get_sequences(cursor)
        assert after['groups'] > before['groups']
        assert after['default'] == before['default']

    def test_it_keeps_its_own_counter_in_step(self, registry):
        registry.ready = True
        registry.setup_signaling()
        before = registry.cache_sequences['stable']
        clear_cache('stable')
        registry.signal_changes()
        assert registry.cache_sequences['stable'] == before + 1

    def test_it_clears_the_flags(self, registry):
        registry.ready = True
        registry.setup_signaling()
        clear_cache('groups')
        registry.signal_changes()
        assert registry.cache_invalidated == set()
        assert registry.registry_invalidated is False

    def test_a_registry_change_bumps_the_registry_table(self, registry, cursor):
        registry.ready = True
        registry.setup_signaling()
        before, _ = registry.get_sequences(cursor)
        registry.registry_invalidated = True
        registry.signal_changes()
        after, _ = registry.get_sequences(cursor)
        # Desigualdad, no ``+ 1``: ver el docstring de
        # ``test_a_second_reader_sees_the_bump`` — un INSERT revertido quema el
        # valor de la SERIAL, asi que ``max(id)`` no es contiguo.
        assert after > before

    def test_a_registry_change_does_not_also_bump_the_caches(self, registry,
                                                             cursor):
        """La fuente lo dice en un comentario: recargar el registro implica
        arrancar con la cache vacia, asi que no se senaliza dos veces.
        """
        registry.ready = True
        registry.setup_signaling()
        _, before = registry.get_sequences(cursor)
        registry.registry_invalidated = True
        clear_cache('groups')
        registry.signal_changes()
        _, after = registry.get_sequences(cursor)
        assert after == before

    def test_it_warns_and_returns_when_the_registry_is_not_ready(self, registry,
                                                                 caplog):
        registry.ready = False
        clear_cache('groups')
        registry.signal_changes()
        assert 'not ready' in caplog.text
        assert registry.cache_invalidated == {'groups'}


class TestCheckSignaling:
    """≙ ``check_signaling`` (``:1076-1108``)."""

    def test_without_changes_it_returns_the_same_registry(self, registry,
                                                          cursor):
        registry.setup_signaling()
        assert registry.check_signaling(cursor) is registry

    def test_a_foreign_cache_bump_invalidates_here(self, registry, cursor):
        """Lo que otro proceso senalizo: la fila la escribe el caso, no este
        registro, y ``check_signaling`` tiene que verla y vaciar su cache.
        """
        registry.setup_signaling()
        cache_of('groups')['clave'] = 'valor'
        cursor.execute("INSERT INTO orm_signaling_groups DEFAULT VALUES")
        registry.check_signaling(cursor)
        assert 'clave' not in cache_of('groups')

    def test_it_takes_the_new_sequence(self, registry, cursor):
        registry.setup_signaling()
        before = registry.cache_sequences['groups']
        cursor.execute("INSERT INTO orm_signaling_groups DEFAULT VALUES")
        registry.check_signaling(cursor)
        assert registry.cache_sequences['groups'] > before

    def test_an_untouched_cache_survives(self, registry, cursor):
        """El control: sin este caso, vaciar TODO ante cualquier senal pasaria
        el positivo de arriba.
        """
        registry.setup_signaling()
        cache_of('assets')['clave'] = 'valor'
        cursor.execute("INSERT INTO orm_signaling_groups DEFAULT VALUES")
        registry.check_signaling(cursor)
        assert cache_of('assets')['clave'] == 'valor'

    def test_a_registry_bump_returns_a_rebuilt_registry(self, registry, cursor):
        registry.setup_signaling()
        cursor.execute("INSERT INTO orm_signaling_registry DEFAULT VALUES")
        rebuilt = registry.check_signaling(cursor)
        assert rebuilt.db_name == registry.db_name
        assert rebuilt.registry_sequence > registry.registry_sequence

    def test_without_a_cursor_it_opens_its_own(self, registry):
        registry.setup_signaling()
        assert registry.check_signaling() is registry


class TestResetChanges:
    """≙ ``reset_changes`` (``:1142-1153``)."""

    def test_it_empties_the_invalidated_caches(self, registry):
        cache_of('groups')['clave'] = 'valor'
        clear_cache('groups')
        cache_of('groups')['clave'] = 'otro'
        registry.reset_changes()
        assert 'clave' not in cache_of('groups')
        assert registry.cache_invalidated == set()

    def test_it_re_runs_the_setup_when_the_registry_changed(self, registry,
                                                            monkeypatch):
        seen = []
        monkeypatch.setattr(Registry, '_setup_models__',
                            lambda self, cr, model_names=None: seen.append(cr))
        registry.registry_invalidated = True
        registry.reset_changes()
        assert len(seen) == 1
        assert registry.registry_invalidated is False

    def test_it_does_nothing_when_nothing_changed(self, registry, monkeypatch):
        """El control: sin este caso, uno que siempre re-ejecutara el setup
        pasaria el positivo.
        """
        seen = []
        monkeypatch.setattr(Registry, '_setup_models__',
                            lambda self, cr, model_names=None: seen.append(cr))
        cache_of('groups')['clave'] = 'valor'
        registry.reset_changes()
        assert seen == []
        assert cache_of('groups')['clave'] == 'valor'


class TestManageChanges:
    """≙ ``manage_changes`` (``:1155-1163``)."""

    def test_it_signals_on_a_clean_exit(self, registry, monkeypatch):
        seen = []
        monkeypatch.setattr(Registry, 'signal_changes',
                            lambda self: seen.append('signal'))
        monkeypatch.setattr(Registry, 'reset_changes',
                            lambda self: seen.append('reset'))
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', DeprecationWarning)
            with registry.manage_changes() as yielded:
                assert yielded is registry
        assert seen == ['signal']

    def test_it_resets_and_re_raises_on_failure(self, registry, monkeypatch):
        seen = []
        monkeypatch.setattr(Registry, 'signal_changes',
                            lambda self: seen.append('signal'))
        monkeypatch.setattr(Registry, 'reset_changes',
                            lambda self: seen.append('reset'))
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', DeprecationWarning)
            with pytest.raises(ValueError):
                with registry.manage_changes():
                    raise ValueError('el cuerpo fallo')
        assert seen == ['reset']

    def test_it_is_deprecated_since_19(self, registry):
        """La fuente lo marca: *"Since 19.0, use signal_changes() and
        reset_changes() directly"*.
        """
        with pytest.warns(DeprecationWarning, match='signal_changes'):
            with registry.manage_changes():
                pass


class TestCursor:
    """≙ ``cursor`` (``:1165-1186``)."""

    def test_it_yields_a_usable_cursor(self, registry):
        with registry.cursor() as cr:
            cr.execute('SELECT 1')
            assert cr.fetchone() == (1,)

    def test_readonly_falls_back_to_the_read_write_cursor(self, registry):
        """La fuente cae al cursor de escritura cuando no hay replica
        (``:1173-1186``); aqui no hay replica declarada, asi que el fallback es
        el camino unico.
        """
        with registry.cursor(readonly=True) as cr:
            cr.execute('SELECT 1')
            assert cr.fetchone() == (1,)


class TestTheReconciledInvalidationRecord:
    """Las dos estructuras de cache eran paralelas y disjuntas — ver el modulo."""

    def test_the_module_invalidator_writes_what_the_signal_reads(self, registry):
        """El control del tramo: ``clear_cache`` y ``cache_invalidated`` tienen
        que ser el MISMO registro. Si vuelven a separarse, este caso cae y
        ninguno de los de ``signal_changes`` lo hace — senalizarian cero sin
        que nada lo delate.
        """
        clear_cache('groups')
        assert 'groups' in registry.cache_invalidated

    def test_clear_all_caches_annotates_every_key(self, registry):
        """Las claves anotadas son EXACTAMENTE las que el eje senaliza.

        ``cache_sequences`` lo puebla ``setup_signaling`` desde las tablas, asi
        que comparar contra sus claves mide que las dos mitades —el
        invalidador de modulo y el eje de senalizacion— hablan del mismo
        conjunto. Un tercer contenedor con otras claves cae aqui.
        """
        registry.setup_signaling()
        clear_all_caches()
        assert registry.cache_invalidated == set(registry.cache_sequences)

    def test_the_record_is_per_thread(self, registry):
        """El control: la anotacion es del hilo que la hizo. Con un conjunto de
        modulo compartido, el hilo veria lo que anoto el principal.
        """
        clear_cache('groups')
        seen = []

        def read():
            seen.append(set(registry.cache_invalidated))

        thread = threading.Thread(target=read)
        thread.start()
        thread.join(timeout=5)
        assert seen == [set()]

    def test_the_live_container_is_the_one_ormcache_reads(self, registry):
        """Una sola estructura: la del proceso, que es la que ``tools.cache``
        pide con ``registry.cache_of``.
        """
        cache_of('groups')['clave'] = 'valor'
        clear_cache('groups')
        assert 'clave' not in cache_of('groups')
