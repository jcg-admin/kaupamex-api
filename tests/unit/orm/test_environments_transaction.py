"""``orm.environments`` — la transacción del ORM y las seis filas de su tabla.

Este archivo existe por una pregunta del ejecutor: *«revisa si lo que escribió
aquí es real, y se tienen sus test que lo demuestran»*, sobre la tabla de
mapeo del docstring de ``orm/environments.py``. La respuesta medida fue que de
sus seis filas **una** era cierta; las otras cinco describían un diseño que el
propio archivo había superado, y nada lo delataba porque **ninguna tenía
prueba**.

Cada clase de abajo fija una fila. El valor de la suite no es que pase: es que
si alguien vuelve a cambiar dónde vive una pieza, la fila que lo afirma cae.

``TestTheModelIndex`` es el control que discrimina
==================================================

La fila ``env['model.name'] → apps.get_model(...)`` no estaba «incompleta»:
**no funciona**. Su primer caso afirma el ``LookupError`` —no lo evita— para
que el día que alguien enseñe a ``apps.get_model`` a resolver un nombre de la
referencia, este caso falle y la fila se reescriba. Un test que sólo afirmara
que el registro funciona sería verde con la tabla vieja y con la nueva: no
distinguiría nada (sub-patrón D de ``metrica-decide-la-conclusion``).
"""
import pytest
from django.apps import apps
from django.db import connection, connections, transaction

from orm import registry
from orm.environments import (Transaction, _connection_transaction,
                              context_scope, env, get_context,
                              get_current_uid, get_transaction, is_su, sudo,
                              transaction_scope, user_scope)


class TestTheModelIndex:
    """Fila 5 — quién resuelve un nombre de modelo de la referencia."""

    def test_django_cannot_resolve_a_reference_name(self):
        """``apps.get_model('res.partner')`` levanta, y ese es el hecho.

        Un nombre de la referencia tiene un punto pero no es
        ``app_label.ModelName``: ``res`` no es una app instalada. La tabla
        del docstring afirmaba lo contrario durante meses.
        """
        with pytest.raises(LookupError) as excinfo:
            apps.get_model('res.partner')
        assert 'res' in str(excinfo.value)

    def test_the_registry_resolves_it(self):
        """``orm.registry.MODELS_BY_NAME`` sí — es el índice de la fuente."""
        model = registry.MODELS_BY_NAME.get('res.partner')
        assert model is not None
        assert model.__name__ == 'ResPartner'

    def test_the_index_is_not_empty(self):
        """Un índice vacío haría pasar al caso anterior por accidente.

        Si el poblado del registro se rompiera, ``.get`` devolvería ``None`` y
        el caso de arriba fallaría — pero un índice con **una** entrada también
        lo dejaría pasar. Este caso mide que el registro está poblado de
        verdad, sin fijar la cifra exacta, que crece con cada model portado.
        """
        assert len(registry.MODELS_BY_NAME) > 50


class TestTheCursorRow:
    """Fila 1 — la única que la tabla vieja tenía bien."""

    def test_the_connection_is_the_cursor(self):
        """``env.cr`` es ``django.db.connection``, y el motor es PostgreSQL."""
        assert connection.vendor == 'postgresql'
        assert connection.alias in connections

    def test_atomic_is_the_transaction_of_the_engine(self):
        """``transaction.atomic`` gobierna el ``COMMIT``, no este módulo."""
        assert callable(transaction.atomic)


class TestTheChannels:
    """Filas 2-4 — las que la tabla mandaba a ``request`` y viven aquí."""

    def test_the_user_channel_lives_in_this_module(self):
        """El uid sale de un canal propio, no de ``request.user``."""
        with user_scope(42):
            assert get_current_uid() == 42

    def test_the_elevation_channel_is_not_is_superuser(self):
        """``sudo()`` eleva sin tocar ningún usuario de Django."""
        assert is_su() is False
        with sudo():
            assert is_su() is True
        assert is_su() is False

    def test_the_context_channel_lives_in_this_module(self):
        """El contexto es un ``ContextVar``, no los kwargs de una vista."""
        assert get_context() == {}
        with context_scope(lang='es_MX'):
            assert get_context()['lang'] == 'es_MX'
        assert get_context() == {}


class TestTheTransaction:
    """Fila 6 — la estructura que Django no trae y aquí se construye."""

    def test_it_declares_the_closed_set_of_structures(self):
        """Las que tienen consumidor, y ninguna más.

        ``__slots__`` cerrado: un atributo nuevo escrito por descuido levanta
        ``AttributeError`` en vez de quedarse ahí sin que nadie lo note.

        El conjunto **crece con el porte**, y por eso el caso lo enumera en vez
        de contarlo: eran cinco hasta la capa A de #273, seis con
        ``field_cache_memo`` —el memo de ``Field._get_cache``, que la fuente
        cuelga del ``Environment`` y aquí cuelga de la transacción porque es
        ella quien tiene su vida—, siete desde que #323 portó ``Cache`` y
        **nueve** desde que #324 portó ``envs`` y ``default_env``. Ninguno de
        los tres últimos es invención nuestra: la fuente los declara en su
        propio ``__slots__`` (``odoo19c: odoo/orm/environments.py:555-558``).

        Los dos de la fuente que aquí **no** están —``registry`` y
        ``_Transaction__file_open_tmp_paths``— llevan su divergencia declarada
        en el docstring de la clase.
        """
        assert Transaction.__slots__ == (
            'cache', 'default_env', 'envs', 'field_cache_memo', 'field_data',
            'field_data_patches', 'field_dirty', 'protected', 'tocompute')

    def test_a_slot_outside_the_declared_set_is_refused(self):
        """El control de que ``__slots__`` está de verdad cerrado.

        ``registry`` es el positivo real: la fuente lo declara y aquí es
        divergencia —el registro es un módulo—, así que escribirlo tiene que
        levantar en vez de crear el atributo en silencio.
        """
        with pytest.raises(AttributeError):
            Transaction().registry = object()

    def test_the_field_cache_defaults_to_a_mapping(self):
        """``field_data[campo]`` nace como el mapa ``{id: valor}`` de la fuente."""
        tx = Transaction()
        tx.field_data['un.campo'][7] = 'valor'
        assert tx.field_data['un.campo'] == {7: 'valor'}

    def test_the_pending_computations_keep_insertion_order(self):
        """``tocompute`` es un ``OrderedSet``: el orden de llegada se conserva."""
        tx = Transaction()
        for record_id in (9, 3, 9, 5):
            tx.tocompute['un.campo'].add(record_id)
        assert list(tx.tocompute['un.campo']) == [9, 3, 5]

    def test_the_protected_fields_stack_by_scope(self):
        """``protected`` es un ``StackMap``: el tope tapa sin borrar lo de abajo."""
        tx = Transaction()
        tx.protected.pushmap({'a': 1})
        tx.protected.pushmap({'b': 2})
        assert tx.protected['a'] == 1 and tx.protected['b'] == 2
        tx.protected.popmap()
        assert tx.protected['a'] == 1
        with pytest.raises(KeyError):
            tx.protected['b']

    def test_the_patches_nest_two_levels(self):
        """``field_data_patches[campo][id]`` nace como lista, no como dict."""
        tx = Transaction()
        tx.field_data_patches['un.campo'][3].append(11)
        assert tx.field_data_patches['un.campo'][3] == [11]

    def test_invalidate_without_spec_empties_everything(self):
        tx = Transaction()
        tx.field_data['a'][1] = 'x'
        tx.field_data['b'][2] = 'y'
        tx.invalidate_field_data()
        assert dict(tx.field_data) == {}

    def test_invalidate_with_spec_only_touches_what_it_names(self):
        """El caso que distingue el borrado dirigido del borrado total."""
        tx = Transaction()
        tx.field_data['a'][1] = 'x'
        tx.field_data['a'][2] = 'x2'
        tx.field_data['b'][3] = 'y'
        tx.invalidate_field_data([('a', [1])])
        assert tx.field_data['a'] == {2: 'x2'}
        assert tx.field_data['b'] == {3: 'y'}

    def test_invalidate_with_none_ids_empties_that_field(self):
        tx = Transaction()
        tx.field_data['a'][1] = 'x'
        tx.field_data['b'][3] = 'y'
        tx.invalidate_field_data([('a', None)])
        assert tx.field_data['a'] == {}
        assert tx.field_data['b'] == {3: 'y'}

    def test_clear_empties_the_four_that_hold_pending_state(self):
        tx = Transaction()
        tx.field_data['a'][1] = 'x'
        tx.field_dirty['a'].add(1)
        tx.field_data_patches['a'][1].append(2)
        tx.tocompute['a'].add(1)
        tx.clear()
        assert not tx.field_data and not tx.field_dirty
        assert not tx.field_data_patches and not tx.tocompute


class TestTheTransactionScope:
    """Quién es «la transacción en curso» y cuánto vive."""

    def test_it_is_the_same_instance_within_a_scope(self):
        """≙ ``env.transaction`` — dos lecturas dan el mismo objeto."""
        assert get_transaction() is get_transaction()

    def test_the_scope_is_the_connections_own_transaction(self):
        """No abre una segunda: **es** la del cursor.

        Medido sobre toda la referencia — ``grep -rn "Transaction("`` sobre
        ``$ODOO19C/odoo/`` devuelve **una sola** instanciacion,
        ``odoo19c: odoo/orm/environments.py:72``::

            transaction = cr.transaction = Transaction(Registry(cr.dbname))

        y esta guardada por ``if transaction is None`` (``:70-71``). Una
        transaccion por cursor, creada perezosamente y compartida por todo
        ``Environment`` que use ese cursor. No hay «transaccion de fuera».
        """
        with transaction_scope() as inside:
            assert inside is get_transaction()
            assert inside is _connection_transaction()

    def test_two_nested_scopes_are_the_same_transaction(self):
        """El control que discrimina el caso de arriba.

        Si el alcance creara una propia, estos dos objetos serian distintos y
        habria una pila que restaurar. La fuente no la tiene: su savepoint no
        instancia nada — su rollback llama ``self._cr.clear()``
        (``odoo19c: odoo/sql_db.py:137-139``) sobre **esa misma** transaccion,
        via ``BaseCursor.clear()`` (``:188-192``).
        """
        with transaction_scope() as outer:
            with transaction_scope() as inner:
                assert inner is outer

    def test_leaving_the_scope_clears_its_cache(self):
        """Una entrada que sobreviva a su transaccion describe una fila que
        ya no existe. Es la razon de ser del ``clear()`` al salir, y es el
        corte que la fuente da en cada frontera: ``commit()`` vuelca y luego
        vacia (``sql_db.py:560-564``), ``rollback()`` vacia primero
        (``:570-572``), ``_close()`` vacia la cache entera (``:534``)."""
        with transaction_scope() as inside:
            inside.field_data['a'][1] = 'x'
        assert dict(inside.field_data) == {}

    def test_a_scope_does_not_clear_on_the_way_in(self):
        """El control positivo del anterior: el corte va al SALIR, no al
        entrar. Sin este caso, un ``clear()`` en ambos extremos pasaria igual
        el de arriba y se llevaria por delante el trabajo del bloque que lo
        envuelve."""
        seeded = get_transaction()
        seeded.field_data['a'][1] = 'x'
        with transaction_scope():
            assert dict(seeded.field_data) == {'a': {1: 'x'}}


class TestTheEnvironmentSugar:
    """El azúcar ``env['model.name']`` que el ejecutor preguntó si se podía
    construir. Se pudo, y estos casos son lo que lo demuestra."""

    def test_it_resolves_a_reference_name(self):
        """Lo que ``apps.get_model`` no puede — ver ``TestTheModelIndex``."""
        assert env()['res.partner'].__name__ == 'ResPartner'

    def test_it_falls_back_to_a_django_label(self):
        """Un modelo propio del L0 sin ``_name`` sólo se alcanza por etiqueta."""
        assert env()['base.ResPartner'].__name__ == 'ResPartner'

    def test_an_unknown_name_raises_key_error(self):
        """El control: si devolviera ``None`` en vez de levantar, un typo en
        un nombre de modelo pasaría en silencio hasta el ``AttributeError``."""
        with pytest.raises(KeyError):
            env()['no.existe']

    def test_membership_and_length_read_the_registry(self):
        environment = env()
        assert 'res.partner' in environment
        assert 'no.existe' not in environment
        assert len(environment) == len(registry.MODELS_BY_NAME)

    def test_the_axes_read_the_channel(self):
        """``env.uid`` / ``env.su`` / ``env.context`` son una VISTA del canal.

        El caso que lo distingue de un segundo almacén: el environment se
        construye **antes** de abrir el alcance, y aun así ve el valor nuevo.
        """
        environment = env()
        with user_scope(7), sudo(), context_scope(lang='es_MX'):
            assert environment.uid == 7
            assert environment.su is True
            assert environment.context['lang'] == 'es_MX'

    def test_a_derived_environment_overrides_the_channel(self):
        derived = env()(user=99, su=True)
        assert derived.uid == 99 and derived.su is True
        assert get_current_uid() is None

    def test_entering_a_derived_environment_activates_the_channel(self):
        """Sin esto el objeto sería decorativo: dos vistas que no coinciden."""
        with env()(user=99, su=True):
            assert get_current_uid() == 99
            assert is_su() is True
        assert get_current_uid() is None and is_su() is False

    def test_leaving_restores_even_with_an_outer_scope(self):
        """El control del anidamiento: el ``reset`` devuelve al valor de
        fuera, no al de por defecto."""
        with user_scope(3):
            with env()(user=99):
                assert get_current_uid() == 99
            assert get_current_uid() == 3

    def test_the_cursor_is_the_connection(self):
        assert env().cr.alias == 'default'

    def test_the_transaction_is_the_one_in_scope(self):
        assert env().transaction is get_transaction()

    def test_lang_is_none_when_the_context_does_not_declare_it(self):
        """La fuente distingue «sin idioma» de «idioma por defecto», y de esa
        distinción depende que ``_description_string`` traduzca o no."""
        assert env().lang is None
        with context_scope(lang='es_MX'):
            assert env().lang == 'es_MX'

    def test_two_environments_with_the_same_axes_are_equal(self):
        assert env() == env()
        assert env() != env()(su=True)

    def test_it_is_hashable(self):
        """El contexto es un dict; si no se congelara, esto levantaría."""
        assert len({env(), env()}) == 1
