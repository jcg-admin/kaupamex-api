"""#324 — los 13 metodos ausentes de ``Environment`` y los 2 de ``Transaction``.

Medido antes de portar nada, con el recorrido AST de las dos clases contra
``odoo19c: odoo/orm/environments.py``::

    Environment: ref 45 | aqui 42 | ausentes 13
    Transaction: ref  5 | aqui  3 | ausentes  2
    Cache:       ref 28 | aqui 28 | ausentes  0   (tarea #323)

Los quince se portan aqui. Tres de ellos cambian de mecanismo y el cambio esta
declarado en su docstring; ninguno se declina.

Los dos controles que discriminan
==================================

1. **``TestTheResetTossesWhatWasMemoized``.** ``Transaction.reset`` llama a
   ``reset_cached_properties`` sobre cada entorno vivo. Si NINGUNA propiedad
   del entorno fuera memorizada, esa llamada seria un no-op y el metodo pasaria
   verde sin hacer nada — el sub-patron D de ``metrica-decide-la-conclusion``.
   El caso mide que ``_field_depends_context`` **si** se memoriza y que el
   ``reset`` **si** lo tira.

2. **``TestTheModelScopedFlush``.** El ``_flush`` anterior arrancaba con
   ``rows = as_record_list(self); if not rows: return``, asi que sobre un
   recordset vacio no escribia nada — y ``flush_model``, que es justo quien lo
   llama sin filas, corria y no volcaba. Los casos de esa clase ensucian el
   cache y vuelcan **sin pasar la fila**, que es lo que la version anterior no
   podia hacer.
"""
import warnings

import pytest
from django.db import connections

from orm import registry
from orm.environments import (Environment, MAX_FIXPOINT_ITERATIONS,
                              context_scope, env, get_current_uid,
                              get_transaction, transaction_scope)
from orm.utils import model_field_registry
from tools.sql import SQL
from tools.translate import _ as lazy_translation

pytestmark = pytest.mark.django_db


@pytest.fixture
def partner_model():
    return registry.MODELS_BY_NAME['res.partner']


class TestTheEnvironmentIsPooledByTransaction:
    """≙ ``Environment.__new__`` (``odoo19c: …/environments.py:64-89``)."""

    def test_two_constructions_with_the_same_axes_give_the_same_object(self):
        with transaction_scope():
            assert Environment(uid=7) is Environment(uid=7)

    def test_differing_axes_give_different_objects(self):
        with transaction_scope():
            assert Environment(uid=7) is not Environment(uid=8)
            assert Environment(uid=7) is not Environment(uid=7, su=True)
            assert Environment(uid=7) is not Environment(uid=7, context={'a': 1})

    def test_the_pool_is_per_transaction(self):
        """Dos transacciones no comparten entorno: el almacen es de la
        transaccion, no del modulo."""
        with transaction_scope():
            first = Environment(uid=7)
        with transaction_scope():
            assert Environment(uid=7) is not first

    def test_the_superuser_uid_elevates_implicitly(self):
        """≙ ``if uid == SUPERUSER_ID: su = True`` (``:66-67``)."""
        with transaction_scope():
            assert Environment(uid=1)._su_override is True

    def test_it_registers_itself_in_the_transaction(self):
        with transaction_scope() as transaction:
            environment = Environment(uid=7)
            alive = [reference() for reference in transaction.envs]
            assert environment in alive

    def test_the_default_env_is_the_first_with_an_integer_uid(self):
        """≙ ``:85-87`` — «the first one with a valid uid»."""
        with transaction_scope() as transaction:
            Environment()                      # sin uid: no es candidato
            assert transaction.default_env is None
            first = Environment(uid=7)
            Environment(uid=9)
            assert transaction.default_env is first

    def test_an_alias_that_is_not_declared_is_refused(self):
        """≙ ``assert isinstance(cr, BaseCursor)`` (``:65``), con la guarda que
        este stack admite: ``cr`` nombra la conexion por su alias."""
        with pytest.raises(AssertionError, match='alias'):
            Environment('una-conexion-que-no-existe')

    def test_every_declared_alias_passes(self):
        for alias in connections:
            assert Environment(alias)._using == alias


class TestTheEnvironmentIsReadOnlyOnceBuilt:
    """≙ ``Environment.__setattr__`` (``:91-95``)."""

    def test_reassigning_an_axis_is_refused(self):
        environment = Environment(uid=7)
        with pytest.raises(AttributeError, match='read-only'):
            environment._uid_override = 9

    def test_the_message_names_the_way_out(self):
        environment = Environment(uid=7)
        with pytest.raises(AttributeError, match=r'call `env\(\)` instead'):
            environment._using = 'default'

    def test_a_memoized_property_is_not_blocked_by_the_guard(self):
        """``functools.cached_property`` escribe en ``__dict__`` sin pasar por
        ``__setattr__``; si pasara, memorizar levantaria."""
        environment = Environment(uid=7)
        assert environment._field_depends_context is not None
        assert '_field_depends_context' in vars(environment)


class TestTheNestedActivationRestoresOneFrameAtATime:
    """El agrupado hace que el mismo objeto pueda estar en dos ``with``."""

    def test_the_outer_override_survives_the_inner_exit(self):
        environment = Environment(uid=7)
        with environment:
            assert get_current_uid() == 7
            with environment:
                assert get_current_uid() == 7
            assert get_current_uid() == 7, (
                'el __exit__ de dentro devolvio tambien el token de fuera')

    def test_leaving_both_restores_the_channel(self):
        before = get_current_uid()
        environment = Environment(uid=7)
        with environment:
            with environment:
                pass
        assert get_current_uid() == before


class TestTheViewsOfTheTransaction:
    """Las cinco vistas: ``_protected``, ``cache``, ``_field_dirty``,
    ``_field_cache_memo`` y ``_field_depends_context``."""

    def test_protected_is_the_stack_of_the_transaction(self):
        assert env()._protected is get_transaction().protected

    def test_cache_is_the_facade_of_the_transaction(self):
        assert env().cache is get_transaction().cache

    def test_field_dirty_is_the_map_of_the_transaction(self):
        assert env()._field_dirty is get_transaction().field_dirty

    def test_field_cache_memo_is_the_memo_of_the_transaction(self):
        assert env()._field_cache_memo is get_transaction().field_cache_memo

    def test_field_depends_context_is_the_map_of_the_registry(self):
        assert env()._field_depends_context is registry.field_depends_context

    def test_the_four_transaction_views_follow_a_new_transaction(self):
        """El control de por que NO estan memorizadas: aqui la transaccion es
        ambiental y una vista memorizada serviria la vieja."""
        environment = Environment(uid=7)
        outer = environment.cache
        with transaction_scope():
            assert environment.cache is not outer
        assert environment.cache is outer


class TestTheResetTossesWhatWasMemoized:
    """El control que le da receptor a ``reset_cached_properties``."""

    def test_the_derived_map_is_memoized(self):
        environment = Environment(uid=7)
        assert environment._field_depends_context is environment._field_depends_context
        assert '_field_depends_context' in vars(environment)

    def test_the_transaction_reset_drops_the_memo_of_every_live_env(self):
        with transaction_scope() as transaction:
            environment = Environment(uid=7)
            environment._field_depends_context  # noqa: B018 — poblar el memo
            assert '_field_depends_context' in vars(environment)
            transaction.reset()
            assert '_field_depends_context' not in vars(environment), (
                'sin esto reset_cached_properties seria un no-op y el reset '
                'pasaria verde sin hacer nada')

    def test_the_reset_clears_the_transaction(self):
        with transaction_scope() as transaction:
            transaction.field_data['a'][1] = 'x'
            transaction.tocompute['b'].add(1)
            transaction.reset()
            assert not transaction.field_data and not transaction.tocompute

    def test_the_environment_reset_delegates_and_warns(self):
        """≙ ``Environment.reset`` (``:59-62``) — obsoleta en 19.0, con aviso."""
        with transaction_scope() as transaction:
            transaction.field_data['a'][1] = 'x'
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always')
                env().reset()
            assert any(issubclass(w.category, DeprecationWarning)
                       for w in caught)
            assert not transaction.field_data


class TestTheTechnicalLanguageCode:
    """≙ ``Environment._lang`` (``:305-313``)."""

    def test_without_a_language_in_the_context_it_falls_back(self):
        assert env()._lang == 'en_US'

    def test_it_takes_the_language_of_the_context(self):
        assert Environment(context={'lang': 'es_MX'})._lang == 'es_MX'

    def test_editing_translations_prefixes_the_underscore(self):
        environment = Environment(context={'lang': 'es_MX',
                                           'edit_translations': True})
        assert environment._lang == '_es_MX'

    def test_checking_translations_prefixes_it_too(self):
        environment = Environment(context={'lang': 'es_MX',
                                           'check_translations': True})
        assert environment._lang == '_es_MX'

    def test_it_is_not_memoized(self):
        """El control de la divergencia declarada: alla el contexto es un
        ``frozendict`` fijado en la construccion y memorizar es seguro; aqui es
        una vista del canal."""
        environment = env()
        assert environment._lang == 'en_US'
        with context_scope(lang='es_MX'):
            assert environment._lang == 'es_MX'


class TestTheTranslationOfTheEnvironment:
    """≙ ``Environment._`` (``:315-348``)."""

    def test_a_plain_string_comes_back(self):
        assert env()._('hello world') == 'hello world'

    def test_positional_arguments_are_substituted(self):
        assert env()._('hello %s', 'test') == 'hello test'

    def test_named_arguments_are_substituted(self):
        assert env()._('hello %(who)s', who='test') == 'hello test'

    def test_mixing_both_forms_is_refused(self):
        with pytest.raises(AssertionError,
                           match='Use args or kwargs, not both'):
            env()._('hello %s', 'a', who='b')

    def test_a_lazy_translation_resolves_to_text(self):
        assert env()._(lazy_translation('hello world')) == 'hello world'

    def test_a_lazy_translation_refuses_extra_arguments(self):
        with pytest.raises(AssertionError,
                           match='All args should come from the lazy text'):
            env()._(lazy_translation('hello %s', 'a'), 'b')

    def test_something_that_is_neither_text_nor_lazy_is_refused(self):
        with pytest.raises(TypeError, match='Cannot translate'):
            env()._(object())


class TestTheModelScopedFlush:
    """``flush_all`` y ``flush_model`` vuelcan el MODELO, sin recibir filas."""

    def _dirty_the_name(self, partner_model, row, value):
        """Ensucia ``name`` en cache como lo dejaria un compute."""
        field = model_field_registry(partner_model)['name']
        field._update_cache([row], value, dirty=True)
        return field

    def test_flush_model_writes_without_being_given_the_row(self,
                                                            partner_model):
        row = partner_model.objects.create(name='antes')
        self._dirty_the_name(partner_model, row, 'despues')
        partner_model.objects.none().flush_model()
        row.refresh_from_db()
        assert row.name == 'despues'

    def test_flush_all_reaches_every_dirty_model(self, partner_model):
        row = partner_model.objects.create(name='antes')
        self._dirty_the_name(partner_model, row, 'por flush_all')
        env().flush_all()
        row.refresh_from_db()
        assert row.name == 'por flush_all'

    def test_the_flush_empties_the_dirty_map(self, partner_model):
        row = partner_model.objects.create(name='antes')
        field = self._dirty_the_name(partner_model, row, 'despues')
        env().flush_all()
        assert not env()._field_dirty.get(field)

    def test_a_clean_transaction_flushes_without_writing(self, partner_model):
        """El caso negativo apunta a una fila que EXISTE: sin nada sucio el
        volcado no la toca."""
        row = partner_model.objects.create(name='intacta')
        env().flush_all()
        row.refresh_from_db()
        assert row.name == 'intacta'

    def test_flush_query_flushes_what_the_query_declares(self, partner_model):
        row = partner_model.objects.create(name='antes')
        field = self._dirty_the_name(partner_model, row, 'por flush_query')
        env().flush_query(SQL('SELECT 1', to_flush=field))
        row.refresh_from_db()
        assert row.name == 'por flush_query'

    def test_a_query_without_metadata_is_a_no_op(self, partner_model):
        row = partner_model.objects.create(name='antes')
        self._dirty_the_name(partner_model, row, 'no deberia escribirse')
        env().flush_query(SQL('SELECT 1'))
        row.refresh_from_db()
        assert row.name == 'antes'


class TestTheTransactionFlush:
    """≙ ``Transaction.flush`` (``:589-598``)."""

    def test_it_delegates_to_the_default_env(self, partner_model):
        row = partner_model.objects.create(name='antes')
        with transaction_scope() as transaction:
            Environment(uid=1)          # fija el default_env
            field = model_field_registry(partner_model)['name']
            field._update_cache([row], 'por transaction.flush', dirty=True)
            transaction.flush()
        row.refresh_from_db()
        assert row.name == 'por transaction.flush'

    def test_without_a_default_env_and_without_envs_it_is_a_no_op(self):
        with transaction_scope() as transaction:
            assert transaction.default_env is None
            transaction.flush()


class TestTheFixpointCeiling:
    """El tope de vueltas es el de la fuente, y el ``for ... else`` avisa."""

    def test_the_ceiling_is_the_one_of_the_source(self):
        assert MAX_FIXPOINT_ITERATIONS == 10

    def test_recompute_all_on_a_clean_transaction_stops_at_once(self, caplog):
        with transaction_scope():
            env()._recompute_all()
        assert 'Too many iterations' not in caplog.text
