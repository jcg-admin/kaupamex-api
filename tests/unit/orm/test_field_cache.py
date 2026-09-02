"""Capa A de #273 — la caché de valores por campo y su recálculo.

Ejerce los ocho símbolos que ``odoo19c: odoo/orm/fields.py:1525-1630`` y
``:1850-1918`` declaran bajo «Cache management methods» y «Computation of
field values»: :meth:`Field._get_cache`, ``_get_cache_impl``,
``_invalidate_cache``, ``_get_all_cache_ids``, ``_insert_cache``,
``_update_cache``, ``recompute`` y ``compute_value``.

El veredicto por símbolo, con el criterio de las dos categorías:

===========================  ==============================================
El stack lo trae hecho       ``collections.deque(maxlen=0)`` para drenar el
                             mapa en C, ``ChainMap`` para fusionar cubos y
                             ``defaultdict`` para el mapa por campo — los
                             tres de ``cpython``, se llaman y ya.
El stack tiene con qué       la caché en sí. Django no tiene ningún almacén
construirlo                  de valor por campo y por transacción; las
                             primitivas están —``Transaction.field_data``
                             ya existía sin consumidor, y ``ContextVar``
                             ancla la transacción— y no hace falta ninguna
                             dependencia de fuera.
===========================  ==============================================
"""
import logging

import pytest
from django.db import models as django_models

import fields
from orm import registry
from orm.environments import env as ambient_env, transaction_scope


class CacheProbe(django_models.Model):
    """Sonda con columna: el caso que la caché tiene que servir."""

    _name = 'orm.cache.probe'

    source = fields.Integer('Source', default=0)
    total = fields.Integer('Total', compute='_compute_total', store=True)

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'orm_cache_probe'

    def _compute_total(self):
        self.total = (self.source or 0) * 2


@pytest.fixture
def open_transaction():
    """Cada caso corre en su propia transacción del ORM, como la fuente."""
    with transaction_scope() as tx:
        yield tx


def field_of(name):
    return CacheProbe._meta.get_field(name)


class TestTheMappingIsStable:
    """``_get_cache`` promete la MISMA instancia entre llamadas."""

    def test_two_calls_return_the_same_mapping(self, open_transaction):
        field = field_of('source')
        first = field._get_cache(ambient_env())
        second = field._get_cache(ambient_env())
        assert first is second

    def test_the_mapping_is_the_one_the_transaction_holds(self, open_transaction):
        field = field_of('source')
        field._get_cache(ambient_env())[7] = 'x'
        assert open_transaction.field_data[field][7] == 'x'

    def test_two_fields_do_not_share_a_mapping(self, open_transaction):
        assert (field_of('source')._get_cache(ambient_env())
                is not field_of('total')._get_cache(ambient_env()))


class TestTheContextSplitsTheCache:
    """Un campo con ``_depends_context`` guarda un cubo por clave."""

    def test_a_plain_field_has_no_bucket(self, open_transaction):
        field = field_of('source')
        field._get_cache(ambient_env())[1] = 'valor'
        assert open_transaction.field_data[field] == {1: 'valor'}

    def test_a_context_field_keys_its_bucket(self, open_transaction, monkeypatch):
        field = field_of('source')
        monkeypatch.setattr(field, '_depends_context', ('bin_size',), raising=False)
        registry.field_depends_context.clear()
        environment = ambient_env()
        field._get_cache(environment)[1] = 'valor'
        assert open_transaction.field_data[field] == {
            environment.cache_key(field): {1: 'valor'}}


class TestInvalidationRemovesWhatItSays:

    def test_without_ids_it_clears_everything(self, open_transaction):
        field = field_of('source')
        field._get_cache(ambient_env()).update({1: 'a', 2: 'b'})
        field._invalidate_cache(ambient_env())
        assert field._get_cache(ambient_env()) == {}

    def test_with_ids_it_pops_only_those(self, open_transaction):
        field = field_of('source')
        field._get_cache(ambient_env()).update({1: 'a', 2: 'b', 3: 'c'})
        field._invalidate_cache(ambient_env(), [1, 3])
        assert field._get_cache(ambient_env()) == {2: 'b'}

    def test_an_absent_id_is_not_an_error(self, open_transaction):
        field = field_of('source')
        field._get_cache(ambient_env())[1] = 'a'
        field._invalidate_cache(ambient_env(), [99])
        assert field._get_cache(ambient_env()) == {1: 'a'}

    def test_an_untouched_field_returns_without_building_a_bucket(self, open_transaction):
        field = field_of('total')
        field._invalidate_cache(ambient_env())
        assert field not in open_transaction.field_data


class TestAllCacheIdsMergesTheBuckets:

    def test_a_plain_field_returns_its_own_mapping(self, open_transaction):
        field = field_of('source')
        field._get_cache(ambient_env()).update({1: 'a', 2: 'b'})
        assert set(field._get_all_cache_ids(ambient_env())) == {1, 2}

    def test_a_context_field_merges_every_bucket(self, open_transaction, monkeypatch):
        field = field_of('source')
        monkeypatch.setattr(field, '_depends_context', ('lang',), raising=False)
        registry.field_depends_context.clear()
        open_transaction.field_data[field] = {('es',): {1: 'a'}, ('en',): {2: 'b'}}
        assert set(field._get_all_cache_ids(ambient_env())) == {1, 2}


class TestInsertKeepsWhatIsAlreadyThere:
    """``_insert_cache`` es ``setdefault``, no asignación: preserva lo pendiente."""

    def test_it_fills_the_missing_ids(self, open_transaction):
        field = field_of('source')
        field._insert_cache(CacheProbe(pk=1), [10])
        assert field._get_cache(ambient_env()) == {1: 10}

    def test_it_does_not_overwrite_a_pending_value(self, open_transaction):
        field = field_of('source')
        field._get_cache(ambient_env())[1] = 'pendiente'
        field._insert_cache([CacheProbe(pk=1), CacheProbe(pk=2)], [10, 20])
        assert field._get_cache(ambient_env()) == {1: 'pendiente', 2: 20}


class TestUpdateWritesAndMarksDirty:

    def test_it_overwrites_every_given_id(self, open_transaction):
        field = field_of('source')
        field._get_cache(ambient_env())[1] = 'viejo'
        field._update_cache([CacheProbe(pk=1), CacheProbe(pk=2)], 'nuevo')
        assert field._get_cache(ambient_env()) == {1: 'nuevo', 2: 'nuevo'}

    def test_dirty_marks_the_stored_column(self, open_transaction):
        field = field_of('source')
        field._update_cache(CacheProbe(pk=1), 5, dirty=True)
        assert 1 in open_transaction.field_dirty[field]

    def test_a_new_record_is_never_dirty(self, open_transaction):
        """La fuente filtra ``if id_`` — un id falsy no se marca."""
        field = field_of('source')
        field._update_cache(CacheProbe(pk=None), 5, dirty=True)
        assert not open_transaction.field_dirty.get(field)

    def test_a_clean_write_over_a_dirty_field_logs_an_error(
            self, open_transaction, caplog):
        """La fuente registra el error; no lanza. Portado igual."""
        field = field_of('source')
        field._update_cache(CacheProbe(pk=1), 5, dirty=True)
        with caplog.at_level(logging.ERROR, logger='orm.fields'):
            field._update_cache(CacheProbe(pk=1), 6)
        assert any(r.levelno == logging.ERROR for r in caplog.records)


class TestRecomputeOnlyTouchesWhatIsPending:

    def test_a_field_with_nothing_pending_does_not_compute(self, open_transaction):
        field = field_of('total')
        record = CacheProbe(pk=1, source=3)
        field.recompute(record)
        assert field not in open_transaction.field_data

    def test_a_pending_id_gets_computed(self, open_transaction):
        field = field_of('total')
        record = CacheProbe(pk=1, source=3)
        ambient_env().add_to_compute(field, [1])
        field.recompute(record)
        assert record.total == 6

    def test_computing_clears_the_pending_mark(self, open_transaction):
        field = field_of('total')
        record = CacheProbe(pk=1, source=3)
        ambient_env().add_to_compute(field, [1])
        field.recompute(record)
        assert not open_transaction.tocompute.get(field)

    def test_a_failing_compute_leaves_the_mark_for_the_next_pass(
            self, open_transaction, monkeypatch):
        field = field_of('total')
        record = CacheProbe(pk=1, source=3)

        def blows_up(self):
            raise ValueError('el cómputo falló')

        monkeypatch.setattr(CacheProbe, '_compute_total', blows_up)
        ambient_env().add_to_compute(field, [1])
        with pytest.raises(ValueError):
            field.compute_value(record)
        assert 1 in open_transaction.tocompute[field]


class TestTheGroupOfFieldsComputedTogether:
    """``field_computed`` agrupa los campos que comparte un mismo método."""

    def test_a_lone_compute_is_its_own_group(self):
        field = field_of('total')
        assert registry.field_computed[field] == [field]

    def test_a_field_without_compute_is_absent(self):
        assert field_of('source') not in registry.field_computed
