"""#328 — los símbolos de nivel 1 de ``odoo/orm/`` que no tenían contraparte.

``scripts/orden_de_porte.py`` mide 40 símbolos en el nivel 1 —los que nada
bloquea y que desbloquean 354 por importación y 909 por llamada— y **11** no
estaban. Los once se portan; ninguno se declina.

======================== ================================ =========================
Símbolo                  En la referencia                  Aquí
======================== ================================ =========================
``attrsetter``           ``decorators.py:73-79``          ``orm/decorators.py``
``check_method_name``    ``utils.py:69-73``               ``orm/utils.py``
``OriginIds``            ``utils.py:129-146``             ``orm/utils.py``
``_unaccent``            ``registry.py:76-81``            ``orm/registry.py``
``parse_read_group_spec``  ``models.py:125-136``          ``orm/models.py``
``RecordCache``          ``models.py:7012-7043``          ``orm/models.py``
``AbstractModel``        ``models.py:7047``               ``orm/models.py``
``Model``                ``models.py:7049-7062``          ``orm/models.py``
``ReversibleComparator`` ``models.py:7066-7094``          ``orm/models.py``
``LangProxyDict``        ``fields_textual.py:706-777``    ``orm/fields_textual.py``
``PrefetchMany2one``     ``fields_relational.py:1734``    ``orm/fields_relational.py``
``PrefetchX2many``       ``fields_relational.py:1757``    ``orm/fields_relational.py``
======================== ================================ =========================

Son doce filas para once símbolos: ``AbstractModel`` y ``Model`` salen del
mismo censo como una sola entrada porque la fuente los declara juntos
(``AbstractModel = BaseModel`` y ``class Model(AbstractModel)``).

Los controles que discriminan, uno por pieza
=============================================

- ``OriginIds`` **filtra**: un id sin origen no se emite
  (``a_new_id_without_origin_is_dropped``). Sin él, devolver la colección
  entera pasaría igual de verde.
- ``_unaccent`` reparte por **tipo**, no por valor; el caso de ``Composable``
  es el que separa nuestro psycopg 3 del psycopg2 de la fuente.
- ``parse_read_group_spec`` **rechaza** lo que no parsea con ``ValueError``;
  sin la guarda saldría un ``AttributeError`` sobre ``None``.
- ``ReversibleComparator`` tiene **dos ejes**, y ``none_first`` NO se invierte
  con ``reverse``: ``test_none_keeps_its_place_under_reverse`` lo mide.
- ``RecordCache`` recorre **sólo lo cacheado**: el modelo declara 128 campos y
  el caso pone dos.
- ``LangProxyDict`` cae a ``en_US`` **sólo** cuando el valor no está en base ni
  se calcula; ``test_a_stored_field_does_not_fall_back`` es el negativo.
- Las dos vistas de prelectura **descartan** el id sin valor cacheado y
  **deduplican**.

Lo que estos dos últimos NO cierran
====================================

``PrefetchMany2one``/``PrefetchX2many`` leen ``record._prefetch_ids``, que en
este árbol **no existe** (medido: 0 apariciones en ``src/``) porque no hay
recordset — el entorno es ambiente y una fila es una instancia de Django. Las
clases se portan enteras contra ese protocolo y se ejercen con un doble; su
consumidor real llega con la tarea **#306**, que recupera el lote de
prelectura.
"""
import collections.abc

import pytest
from django.db import models as django_models
from psycopg import sql as pg_sql

from exceptions import AccessError
from orm import registry
from orm.decorators import attrsetter
from orm.environments import transaction_scope
from orm.fields_relational import PrefetchMany2one, PrefetchX2many
from orm.fields_textual import LangProxyDict
from orm.identifiers import NewId
from orm.models import (AbstractModel, Model, RecordCache,
                        ReversibleComparator, parse_read_group_spec)
from orm.registry import _unaccent
from orm.utils import OriginIds, check_method_name, model_field_registry
from tools.sql import SQL


class TestAttrsetterMarksTheMethodAndReturnsIt:
    """≙ ``attrsetter`` (``odoo19c: odoo/orm/decorators.py:73-79``)."""

    def test_it_sets_the_attribute(self):
        def method():
            pass
        assert attrsetter('_marca', 'valor')(method) is method
        assert method._marca == 'valor'

    def test_it_returns_the_same_object_so_it_composes(self):
        """Devolver el método es lo que permite apilarlo como decorador."""
        @attrsetter('_uno', 1)
        @attrsetter('_dos', 2)
        def method():
            pass
        assert (method._uno, method._dos) == (1, 2)

    def test_the_setter_is_reusable(self):
        setter = attrsetter('_marca', 'valor')

        def first():
            pass

        def second():
            pass
        setter(first), setter(second)
        assert first._marca == second._marca == 'valor'


class TestCheckMethodNameRefusesThePrivateName:
    """≙ ``check_method_name`` (``utils.py:69-73``)."""

    def test_a_public_name_passes(self):
        with pytest.warns(DeprecationWarning):
            assert check_method_name('action_confirm') is None

    def test_an_underscore_name_is_refused(self):
        with pytest.warns(DeprecationWarning), pytest.raises(AccessError):
            check_method_name('_compute_total')

    def test_init_is_refused_too(self):
        """La fuente lo mete en el mismo patrón — ``^(_.*|init)$``."""
        with pytest.warns(DeprecationWarning), pytest.raises(AccessError):
            check_method_name('init')

    def test_the_message_names_the_method(self):
        with pytest.warns(DeprecationWarning), pytest.raises(AccessError) as failure:
            check_method_name('_secreto')
        assert '_secreto' in str(failure.value)

    def test_it_warns_that_it_is_deprecated_since_19(self):
        with pytest.warns(DeprecationWarning, match='Since 19.0'):
            check_method_name('action_confirm')


class TestOriginIdsYieldsTheOriginOfEachId:
    """≙ ``OriginIds`` (``utils.py:129-146``) — «A reversible iterable
    returning the origin ids of a collection of ``ids``»."""

    def test_a_real_id_comes_through_as_is(self):
        assert list(OriginIds([1, 2, 3])) == [1, 2, 3]

    def test_a_new_id_yields_its_origin(self):
        assert list(OriginIds([NewId(origin=7)])) == [7]

    def test_a_new_id_without_origin_is_dropped(self):
        """El control que discrimina: si no filtrara, esto devolvería el
        ``NewId`` y el caso pasaría igual."""
        assert list(OriginIds([NewId()])) == []

    def test_it_mixes_both_kinds_preserving_order(self):
        assert list(OriginIds([1, NewId(origin=7), NewId(), 3])) == [1, 7, 3]

    def test_it_is_reversible(self):
        assert list(reversed(OriginIds([1, NewId(origin=7), 3]))) == [3, 7, 1]

    def test_the_reverse_filters_the_same_way(self):
        assert list(reversed(OriginIds([1, NewId(), 3]))) == [3, 1]

    def test_it_can_be_walked_twice(self):
        """No es un generador: guarda la colección, no su recorrido."""
        origins = OriginIds([1, NewId(origin=7)])
        assert list(origins) == list(origins) == [1, 7]


class TestUnaccentWrapsByType:
    """≙ ``_unaccent`` (``registry.py:76-81``)."""

    def test_a_plain_string_comes_back_as_a_string(self):
        assert _unaccent('name') == 'unaccent(name)'

    def test_a_sql_wrapper_comes_back_as_a_sql_wrapper(self):
        wrapped = _unaccent(SQL('%s', 'x'))
        assert isinstance(wrapped, SQL)
        assert 'unaccent' in wrapped.code

    def test_a_composable_comes_back_composed(self):
        """La rama que separa nuestro psycopg 3 del psycopg2 de la fuente:
        el tipo es el mismo nombre y otro paquete."""
        wrapped = _unaccent(pg_sql.Identifier('name'))
        assert isinstance(wrapped, pg_sql.Composed)

    def test_the_sql_branch_keeps_the_parameters(self):
        wrapped = _unaccent(SQL('%s', 'buscado'))
        assert wrapped.params == ['buscado']


class TestParseReadGroupSpecSplitsTheThreeParts:
    """≙ ``parse_read_group_spec`` (``models.py:125-136``) — devuelve el
    triplete ``(campo, nombre_de_propiedad, agregado)``."""

    def test_a_bare_field_gives_only_the_name(self):
        assert parse_read_group_spec('quantity') == ('quantity', None, None)

    def test_the_colon_separates_the_aggregate(self):
        assert parse_read_group_spec('quantity:sum') == ('quantity', None, 'sum')

    def test_the_dot_separates_the_property(self):
        assert parse_read_group_spec('properties.color') == (
            'properties', 'color', None)

    def test_it_reads_the_three_parts_at_once(self):
        assert parse_read_group_spec('properties.date:month') == (
            'properties', 'date', 'month')

    def test_a_nested_property_keeps_its_dots(self):
        assert parse_read_group_spec('properties.a.b:day') == (
            'properties', 'a.b', 'day')

    def test_an_unparseable_spec_is_refused(self):
        """El control que discrimina: sin la guarda, ``res_match`` seria
        ``None`` y el acceso a ``.groups()`` reventaria con ``AttributeError``
        en vez del ``ValueError`` que la fuente promete."""
        with pytest.raises(ValueError, match='Invalid aggregate/groupby'):
            parse_read_group_spec('no me parseo')


class TestReversibleComparatorOrdersWithNoneAndDirection:
    """≙ ``ReversibleComparator`` (``models.py:7066-7094``)."""

    def _sorted(self, values, reverse=False, none_first=False):
        return sorted(values, key=lambda v: ReversibleComparator(
            v, reverse=reverse, none_first=none_first))

    def test_it_sorts_ascending_by_default(self):
        assert self._sorted([3, 1, 2]) == [1, 2, 3]

    def test_reverse_flips_the_order_inside_the_key(self):
        """No es ``sorted(reverse=True)``: la direccion viaja en la clave, que
        es lo que permite mezclar columnas ascendentes y descendentes."""
        assert self._sorted([3, 1, 2], reverse=True) == [3, 2, 1]

    def test_none_goes_last_by_default(self):
        assert self._sorted([3, None, 1]) == [1, 3, None]

    def test_none_first_moves_it_to_the_head(self):
        assert self._sorted([3, None, 1], none_first=True) == [None, 1, 3]

    def test_none_keeps_its_place_under_reverse(self):
        """El control que discrimina: ``none_first`` NO se invierte con
        ``reverse`` — son dos ejes. Sin la rama propia del ``None``, la
        inversion lo arrastraria."""
        assert self._sorted([3, None, 1], reverse=True) == [3, 1, None]
        assert self._sorted([3, None, 1], reverse=True,
                            none_first=True) == [None, 3, 1]

    def test_two_nones_compare_equal(self):
        first = ReversibleComparator(None, reverse=False, none_first=True)
        second = ReversibleComparator(None, reverse=False, none_first=True)
        assert first == second
        assert not (first < second)

    def test_it_hashes_by_the_item(self):
        assert (hash(ReversibleComparator(7, reverse=False, none_first=False))
                == hash(7))

    def test_the_repr_names_the_direction(self):
        shown = repr(ReversibleComparator(7, reverse=True, none_first=False))
        assert shown == '<ReversibleComparator 7 reverse>'

    def test_total_ordering_gives_the_other_three_operators(self):
        """``@functools.total_ordering`` deriva ``<=``, ``>`` y ``>=`` de
        ``__lt__`` y ``__eq__``; la fuente cuenta con ello."""
        small = ReversibleComparator(1, reverse=False, none_first=False)
        big = ReversibleComparator(2, reverse=False, none_first=False)
        assert small <= big and big > small and big >= small


@pytest.mark.django_db
class TestRecordCacheReadsTheCacheOfOneRow:
    """≙ ``RecordCache`` (``models.py:7012-7043``) — «A mapping from field
    names to values, to read the cache of a record»."""

    def _cached(self, row, field_name, value):
        field = model_field_registry(type(row))[field_name]
        field._update_cache([row], value, dirty=True)
        return field

    def test_a_cached_field_is_readable_by_name(self):
        with transaction_scope():
            row = registry.MODELS_BY_NAME['res.partner'](pk=101)
            self._cached(row, 'name', 'Acme')
            assert RecordCache(row)['name'] == 'Acme'

    def test_membership_answers_for_the_cached_field(self):
        with transaction_scope():
            row = registry.MODELS_BY_NAME['res.partner'](pk=102)
            self._cached(row, 'name', 'Acme')
            cached = RecordCache(row)
            assert 'name' in cached and 'email' not in cached

    def test_an_uncached_field_raises_key_error(self):
        with transaction_scope():
            row = registry.MODELS_BY_NAME['res.partner'](pk=103)
            with pytest.raises(KeyError):
                RecordCache(row)['email']

    def test_a_name_that_is_not_a_field_raises_key_error_too(self):
        """La fuente hace ``record._fields[name]`` sin guarda: un nombre que
        no es campo revienta con ``KeyError``, no responde ``False``."""
        with transaction_scope():
            row = registry.MODELS_BY_NAME['res.partner'](pk=109)
            with pytest.raises(KeyError):
                'no_soy_un_campo' in RecordCache(row)

    def test_it_iterates_only_the_cached_names(self):
        """El control que discrimina: el modelo declara 128 campos y sólo dos
        están en caché. Un recorrido que devolviera ``_fields`` entero pasaría
        los casos de lectura y fallaría aquí."""
        with transaction_scope():
            row = registry.MODELS_BY_NAME['res.partner'](pk=104)
            self._cached(row, 'name', 'Acme')
            self._cached(row, 'email', 'a@b.mx')
            assert sorted(RecordCache(row)) == ['email', 'name']

    def test_its_length_counts_the_cached_ones(self):
        with transaction_scope():
            row = registry.MODELS_BY_NAME['res.partner'](pk=105)
            self._cached(row, 'name', 'Acme')
            assert len(RecordCache(row)) == 1

    def test_the_cache_of_one_row_does_not_leak_into_another(self):
        with transaction_scope():
            first = registry.MODELS_BY_NAME['res.partner'](pk=106)
            second = registry.MODELS_BY_NAME['res.partner'](pk=107)
            self._cached(first, 'name', 'Acme')
            assert 'name' in RecordCache(first)
            assert 'name' not in RecordCache(second)

    def test_it_is_a_mapping(self):
        with transaction_scope():
            row = registry.MODELS_BY_NAME['res.partner'](pk=108)
            self._cached(row, 'name', 'Acme')
            assert dict(RecordCache(row)) == {'name': 'Acme'}


class TestTheTwoModelBases:
    """≙ ``AbstractModel``/``Model`` (``models.py:7047-7062``).

    La fuente los declara como dos clases: ``AbstractModel = BaseModel``
    —``_auto`` ``False``, ``_abstract`` ``True``— y ``class Model(AbstractModel)``
    que invierte los tres. Aquí ``Model`` **ya es** la base persistida —el
    ``models.Model`` de Django que este módulo re-exporta y al que
    ``models_transient.py`` hereda—, así que lo que faltaba era el hermano
    abstracto.
    """

    def test_the_persisted_base_is_the_one_django_gives(self):
        """El control que discrimina: si alguien declarara aquí un ``class
        Model`` propio, este caso caería — y con él caería en silencio el
        ``TransientModel`` que hereda del re-exportado."""
        assert Model is django_models.Model

    def test_the_abstract_base_declares_the_four_of_the_source(self):
        assert (AbstractModel._auto, AbstractModel._register,
                AbstractModel._abstract, AbstractModel._name) == (
                    False, False, True, None)

    def test_the_abstract_base_is_not_a_django_model(self):
        """Y no puede serlo: un registrante sin tabla es justo lo que
        ``registrants_without_table`` cuenta apartando a los que tienen
        ``_meta``. Heredar de Django le daría uno y lo sacaría de esa cuenta.
        """
        assert not issubclass(AbstractModel, django_models.Model)
        assert not hasattr(AbstractModel, '_meta')

    def test_it_is_the_base_of_the_two_registrants_without_table(self):
        """Sus consumidores medidos: los dos que declaran ``_name`` y no
        tienen tabla."""
        sin_tabla = dict(registry.registrants_without_table())
        assert set(sin_tabla) == {'IrFieldsConverter', 'IrTemplateExpressions'}


class _StringFieldDouble:
    """El mínimo que :class:`LangProxyDict` consulta de su campo: ``compute``
    y ``store``. Un doble y no un campo real porque la clase reparte por esos
    dos atributos, no por el tipo."""

    def __init__(self, compute=None, store=True):
        self.compute = compute
        self.store = store


class TestLangProxyDictViewsOneLanguageOfTheCache:
    """≙ ``LangProxyDict`` (``fields_textual.py:706-777``) — «A view on a
    dict[id, dict[lang, value]] that maps id to value given a fixed
    language»."""

    def _view(self, cache, lang='es_MX', **field):
        return LangProxyDict(_StringFieldDouble(**field), cache, lang)

    def test_it_reads_the_value_of_its_language(self):
        view = self._view({1: {'es_MX': 'hola', 'en_US': 'hi'}})
        assert view[1] == 'hola' and view.get(1) == 'hola'

    def test_a_stored_field_does_not_fall_back(self):
        """El control que discrimina: con la fila en base y el idioma ausente,
        la fuente NO cae a ``en_US`` — ``vals[self._lang]``. Sin esa rama, este
        caso devolvería ``'hi'`` y pasaría igual de verde."""
        view = self._view({1: {'en_US': 'hi'}})
        with pytest.raises(KeyError):
            view[1]
        assert view.get(1, 'nada') == 'nada'

    def test_a_field_without_column_falls_back_to_the_base_locale(self):
        view = self._view({1: {'en_US': 'hi'}}, store=False)
        assert view[1] == 'hi' and view.get(1) == 'hi'

    def test_a_new_id_without_origin_falls_back_too(self):
        """``key or key.origin`` — el registro nuevo sin origen no está en
        base, así que se comporta como el campo sin columna."""
        key = NewId()
        view = self._view({key: {'en_US': 'hi'}})
        assert view[key] == 'hi'

    def test_a_computed_field_does_not_fall_back(self):
        view = self._view({1: {'en_US': 'hi'}}, compute='_compute_name',
                          store=False)
        with pytest.raises(KeyError):
            view[1]

    def test_a_none_value_comes_back_as_none(self):
        view = self._view({1: None})
        assert view[1] is None and view.get(1) is None

    def test_a_missing_key_gives_the_default(self):
        assert self._view({}).get(1, 'nada') == 'nada'

    def test_writing_creates_the_language_bucket(self):
        cache = {}
        self._view(cache)[1] = 'hola'
        assert cache == {1: {'es_MX': 'hola'}}

    def test_writing_a_field_without_column_seeds_the_base_locale(self):
        cache = {}
        self._view(cache, store=False)[1] = 'hola'
        assert cache == {1: {'es_MX': 'hola', 'en_US': 'hola'}}

    def test_writing_none_wipes_the_whole_bucket(self):
        cache = {1: {'es_MX': 'hola', 'en_US': 'hi'}}
        self._view(cache)[1] = None
        assert cache == {1: None}

    def test_deleting_pops_only_its_language(self):
        cache = {1: {'es_MX': 'hola', 'en_US': 'hi'}}
        del self._view(cache)[1]
        assert cache == {1: {'en_US': 'hi'}}

    def test_it_iterates_the_keys_of_its_language(self):
        view = self._view({1: {'es_MX': 'hola'}, 2: {'en_US': 'hi'}, 3: None})
        assert sorted(view) == [1, 3]
        assert len(view) == 2

    def test_clear_pops_its_language_from_every_bucket(self):
        cache = {1: {'es_MX': 'hola', 'en_US': 'hi'}, 2: {'es_MX': 'adios'}}
        self._view(cache).clear()
        assert cache == {1: {'en_US': 'hi'}, 2: {}}

    def test_the_repr_names_the_language_and_the_size(self):
        shown = repr(self._view({1: {'es_MX': 'hola'}}))
        assert shown.startswith("<LangProxyDict lang='es_MX' size=1 at 0x")


class _PrefetchRecordDouble:
    """El mínimo que las dos vistas de prelectura consultan del registro: su
    conjunto de prelectura. Es un doble porque el conjunto real todavía no
    existe en este árbol — ver la tarea **#306**."""

    def __init__(self, prefetch_ids):
        self._prefetch_ids = prefetch_ids


class _CachedFieldDouble:
    def __init__(self, cache):
        self._cache = cache

    def _get_cache(self, environment):
        return self._cache


@pytest.mark.django_db
class TestThePrefetchViewsWalkTheCacheOfTheSet:
    """≙ ``PrefetchMany2one``/``PrefetchX2many``
    (``fields_relational.py:1734-1779``)."""

    def test_the_many2one_view_yields_the_coids_in_order(self):
        with transaction_scope():
            view = PrefetchMany2one(_PrefetchRecordDouble([1, 2, 3]),
                                    _CachedFieldDouble({1: 10, 2: 20, 3: 30}))
            assert list(view) == [10, 20, 30]

    def test_the_many2one_view_drops_the_id_with_no_cached_value(self):
        """El control que discrimina: sin el ``is not None``, el hueco saldría
        como ``None`` en vez de desaparecer."""
        with transaction_scope():
            view = PrefetchMany2one(_PrefetchRecordDouble([1, 2, 3]),
                                    _CachedFieldDouble({1: 10, 3: 30}))
            assert list(view) == [10, 30]

    def test_the_many2one_view_deduplicates(self):
        with transaction_scope():
            view = PrefetchMany2one(_PrefetchRecordDouble([1, 2, 3]),
                                    _CachedFieldDouble({1: 10, 2: 10, 3: 30}))
            assert list(view) == [10, 30]

    def test_the_many2one_view_is_reversible(self):
        with transaction_scope():
            view = PrefetchMany2one(_PrefetchRecordDouble([1, 2, 3]),
                                    _CachedFieldDouble({1: 10, 2: 20, 3: 30}))
            assert list(reversed(view)) == [30, 20, 10]

    def test_the_x2many_view_flattens_each_collection(self):
        with transaction_scope():
            view = PrefetchX2many(_PrefetchRecordDouble([1, 2]),
                                  _CachedFieldDouble({1: (10, 11), 2: (20,)}))
            assert list(view) == [10, 11, 20]

    def test_the_x2many_view_treats_a_missing_id_as_empty(self):
        with transaction_scope():
            view = PrefetchX2many(_PrefetchRecordDouble([1, 2, 3]),
                                  _CachedFieldDouble({1: (10,), 3: (30,)}))
            assert list(view) == [10, 30]

    def test_the_x2many_view_deduplicates_across_collections(self):
        with transaction_scope():
            view = PrefetchX2many(_PrefetchRecordDouble([1, 2]),
                                  _CachedFieldDouble({1: (10, 11), 2: (11, 12)}))
            assert list(view) == [10, 11, 12]

    def test_the_x2many_view_is_reversible(self):
        with transaction_scope():
            view = PrefetchX2many(_PrefetchRecordDouble([1, 2]),
                                  _CachedFieldDouble({1: (10, 11), 2: (20,)}))
            assert list(reversed(view)) == [20, 10, 11]

    def test_both_are_reversible_iterables(self):
        """La fuente los declara ``Reversible`` (``fields_relational.py:7`` —
        ``from collections.abc import Reversible``)."""
        assert issubclass(PrefetchMany2one, collections.abc.Reversible)
        assert issubclass(PrefetchX2many, collections.abc.Reversible)
