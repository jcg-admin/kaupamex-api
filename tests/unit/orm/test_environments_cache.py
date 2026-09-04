"""``Cache`` y ``Starred`` — la fachada de la caché de la transacción (#323).

``odoo19c: odoo/orm/environments.py:638-954`` declara ``Cache``: **28 métodos**
sobre el almacén que la transacción ya sostiene. Aquí ese almacén existía desde
:ref:`h-api-1025` (``Transaction.field_data`` y sus hermanos) y sus escritores
también (``Field._get_cache`` y compañía, ``src/orm/fields.py:2336-2460``); lo
que faltaba era la **fachada** que la fuente pone encima y que sus consumidores
llaman por nombre.

El veredicto por símbolo, con el criterio de las dos categorías:

===========================  ==============================================
El stack lo trae hecho       ``warnings.warn`` para la superficie obsoleta,
                             ``frozendict`` —ya portado en #325— para el
                             centinela ``EMPTY_DICT``, y el mapa por campo
                             que ``Transaction`` ya guarda.
El stack tiene con qué       la fachada entera. Django no tiene caché por
construirlo                  transacción, así que ``Cache`` no adapta nada
                             suyo: se escribe sobre las primitivas que este
                             árbol ya construyó.
===========================  ==============================================

Las tres divergencias de mecanismo que estos casos fijan
========================================================

1. **El entorno es ambiental.** La fuente resuelve la caché por
   ``model.env``; aquí el entorno es una vista de ``contextvars``
   (``orm.environments.env``), así que el parámetro ``model`` de
   ``_get_field_cache``/``_set_field_cache`` conserva la firma y **no** decide
   el entorno.
2. **No hay recordset.** Donde la fuente escribe ``record._ids``, aquí va
   ``record_ids(records)``; donde escribe ``model.browse(ids)``, va
   ``browse(model, ids)`` — el par que :ref:`h-api-1046` ya declaró.
3. **El registro es un módulo.** ``self.transaction.registry`` no existe: el
   mapa derivado vive en ``orm.registry.field_depends_context``.

Qué haría fallar a estos casos
==============================

El control que discrimina es ``test_the_deprecated_surface_warns``: los diez
métodos que la fuente marca obsoletos abren con ``warnings.warn``, y un porte
que los escribiera sin el aviso pasaría cualquier caso que sólo midiera su
valor de retorno. Aquí el aviso **es** parte del contrato portado, así que se
mide con ``pytest.warns`` uno por uno.
"""
import warnings

import pytest
from django.db import models as django_models

import fields
from addons.base.models.res_partner import ResPartner
from exceptions import CacheMiss
from orm import registry
from orm.environments import (EMPTY_DICT, MAX_FIXPOINT_ITERATIONS, Cache,
                              Starred, env as ambient_env, transaction_scope)
from orm.fields_nonstored import non_stored_fields
from orm.utils import record_ids
from tools.misc import frozendict


class CacheFacadeProbe(django_models.Model):
    """Sonda con columna: el caso que la fachada tiene que servir."""

    _name = 'orm.cache.facade.probe'

    source = fields.Integer('Source', default=0)
    label = fields.Char('Label', size=64)

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'orm_cache_facade_probe'


@pytest.fixture
def open_transaction():
    """Cada caso corre en su propia transacción del ORM, como la fuente."""
    with transaction_scope() as tx:
        yield tx


def field_of(name):
    return CacheFacadeProbe._meta.get_field(name)


class TestTheModuleConstants:
    """Los dos valores que la fuente declara junto a ``Cache``."""

    def test_the_fixpoint_bound_is_the_one_of_the_source(self):
        """``MAX_FIXPOINT_ITERATIONS = 10`` (``odoo19c: …:37``)."""
        assert MAX_FIXPOINT_ITERATIONS == 10

    def test_the_empty_sentinel_is_an_immutable_mapping(self):
        """``EMPTY_DICT = frozendict()`` (``:635``) — parámetro opcional que
        nadie puede mutar por accidente."""
        assert isinstance(EMPTY_DICT, frozendict)
        assert EMPTY_DICT == {}
        # ``NotImplementedError`` y no ``TypeError``: los siete mutadores de
        # ``frozendict`` lo levantan con el nombre de la operación dentro
        # (``odoo19c: odoo/tools/misc.py:963-982``), y el porte lo copia
        # verbatim. El mensaje entra en la aserción porque es lo que distingue
        # el centinela de un ``dict`` cualquiera, que aceptaría la escritura.
        with pytest.raises(NotImplementedError) as failure:
            EMPTY_DICT['x'] = 1
        assert '__setitem__' in str(failure.value)


class TestTheStarredMarksTheValue:
    """``Starred`` (``:956``) — el sufijo de estrella del ``repr`` sucio."""

    def test_the_repr_appends_the_star(self):
        assert repr(Starred(7)) == '7*'

    def test_the_repr_of_the_value_is_the_one_used(self):
        """Es ``repr`` del valor, no ``str``: una cadena sale entrecomillada."""
        assert repr(Starred('a')) == "'a'*"

    def test_the_slots_keep_it_light(self):
        """``__slots__ = ['value']`` — sin ``__dict__``."""
        with pytest.raises(AttributeError):
            Starred(1).other = 2


class TestTheTransactionOwnsItsCache:
    """``Transaction.__init__`` termina con ``self.cache = Cache(self)``."""

    def test_the_transaction_exposes_a_cache(self, open_transaction):
        assert isinstance(open_transaction.cache, Cache)

    def test_the_cache_points_back_at_its_transaction(self, open_transaction):
        assert open_transaction.cache.transaction is open_transaction

    def test_the_cache_is_the_same_object_between_reads(self, open_transaction):
        assert open_transaction.cache is open_transaction.cache


class TestTheCacheReadsAndWritesOneValue:
    """``set`` · ``get`` · ``contains`` · ``remove`` sobre una fila."""

    def test_what_is_set_is_read_back(self, open_transaction):
        record, field = CacheFacadeProbe(pk=1), field_of('source')
        open_transaction.cache.set(record, field, 42)
        assert open_transaction.cache.get(record, field) == 42

    def test_contains_answers_for_the_record(self, open_transaction):
        record, field = CacheFacadeProbe(pk=1), field_of('source')
        assert not open_transaction.cache.contains(record, field)
        open_transaction.cache.set(record, field, 1)
        assert open_transaction.cache.contains(record, field)

    def test_a_miss_raises_cache_miss(self, open_transaction):
        """Sin valor y sin ``default``, la fuente levanta ``CacheMiss``."""
        with pytest.raises(CacheMiss):
            open_transaction.cache.get(CacheFacadeProbe(pk=9), field_of('source'))

    def test_a_miss_returns_the_given_default(self, open_transaction):
        got = open_transaction.cache.get(
            CacheFacadeProbe(pk=9), field_of('source'), default='sin valor')
        assert got == 'sin valor'

    def test_remove_drops_the_value(self, open_transaction):
        record, field = CacheFacadeProbe(pk=1), field_of('source')
        open_transaction.cache.set(record, field, 5)
        open_transaction.cache.remove(record, field)
        assert not open_transaction.cache.contains(record, field)

    def test_remove_of_an_absent_value_is_silent(self, open_transaction):
        """La fuente traga el ``KeyError`` — borrar lo que no está no es error."""
        open_transaction.cache.remove(CacheFacadeProbe(pk=9), field_of('source'))


class TestTheCacheWorksOnSeveralRecords:
    """``update`` · ``update_raw`` · ``get_values`` · ``get_missing_ids``."""

    def test_update_writes_one_value_per_record(self, open_transaction):
        records = [CacheFacadeProbe(pk=1), CacheFacadeProbe(pk=2)]
        field = field_of('source')
        open_transaction.cache.update(records, field, [10, 20])
        assert list(open_transaction.cache.get_values(records, field)) == [10, 20]

    def test_update_raw_writes_the_same_without_the_language_logic(
            self, open_transaction):
        records = [CacheFacadeProbe(pk=1), CacheFacadeProbe(pk=2)]
        field = field_of('label')
        open_transaction.cache.update_raw(records, field, ['a', 'b'])
        assert list(open_transaction.cache.get_values(records, field)) == ['a', 'b']

    def test_get_values_skips_what_is_not_cached(self, open_transaction):
        """La fuente hace ``continue`` ante un ``KeyError``, no rellena."""
        field = field_of('source')
        open_transaction.cache.set(CacheFacadeProbe(pk=2), field, 20)
        records = [CacheFacadeProbe(pk=1), CacheFacadeProbe(pk=2)]
        assert list(open_transaction.cache.get_values(records, field)) == [20]

    def test_get_missing_ids_names_the_ones_without_value(self, open_transaction):
        field = field_of('source')
        open_transaction.cache.set(CacheFacadeProbe(pk=2), field, 20)
        records = [CacheFacadeProbe(pk=1), CacheFacadeProbe(pk=2)]
        assert list(open_transaction.cache.get_missing_ids(records, field)) == [1]


class TestTheCacheAnswersAboutTheField:
    """``contains_field`` · ``get_fields`` — las preguntas de barrido."""

    def test_contains_field_is_false_before_any_write(self, open_transaction):
        assert not open_transaction.cache.contains_field(field_of('source'))

    def test_contains_field_is_true_after_one_write(self, open_transaction):
        field = field_of('source')
        open_transaction.cache.set(CacheFacadeProbe(pk=1), field, 1)
        assert open_transaction.cache.contains_field(field)

    def test_get_fields_names_only_what_has_a_value(self, open_transaction):
        record = CacheFacadeProbe(pk=1)
        open_transaction.cache.set(record, field_of('source'), 1)
        names = {f.name for f in open_transaction.cache.get_fields(record)}
        assert names == {'source'}


class TestTheDirtyFlagIsVisible:
    """La marca de sucio: el ``repr`` con estrella y la superficie que la lee."""

    def test_the_repr_stars_the_dirty_id(self, open_transaction):
        field = field_of('source')
        open_transaction.cache.set(CacheFacadeProbe(pk=1), field, 7, dirty=True)
        assert '7' in repr(open_transaction.cache)
        assert '1*' in repr(open_transaction.cache)

    def test_the_repr_leaves_the_clean_id_alone(self, open_transaction):
        field = field_of('source')
        open_transaction.cache.set(CacheFacadeProbe(pk=1), field, 7)
        assert '1*' not in repr(open_transaction.cache)


class TestTheInvalidationClearsWhatItSays:
    """``invalidate`` · ``clear`` — el alcance de cada uno."""

    def test_invalidate_without_spec_empties_everything(self, open_transaction):
        field = field_of('source')
        open_transaction.cache.set(CacheFacadeProbe(pk=1), field, 1)
        open_transaction.cache.invalidate()
        assert not open_transaction.cache.contains_field(field)

    def test_invalidate_with_spec_only_touches_the_named_ids(
            self, open_transaction):
        field = field_of('source')
        open_transaction.cache.set(CacheFacadeProbe(pk=1), field, 1)
        open_transaction.cache.set(CacheFacadeProbe(pk=2), field, 2)
        open_transaction.cache.invalidate([(field, [1])])
        assert not open_transaction.cache.contains(CacheFacadeProbe(pk=1), field)
        assert open_transaction.cache.contains(CacheFacadeProbe(pk=2), field)

    def test_clear_also_drops_the_dirty_flags(self, open_transaction):
        """``invalidate`` deja la marca de sucio; ``clear`` la borra — es la
        distinción que la fuente escribe entre los dos métodos."""
        field = field_of('source')
        open_transaction.cache.set(CacheFacadeProbe(pk=1), field, 1, dirty=True)
        open_transaction.cache.clear()
        assert not open_transaction.field_dirty.get(field)


class TestTheDeprecatedSurfaceWarns:
    """Los diez que la fuente marca obsoletos abren con ``warnings.warn``.

    Es el control que discrimina: un porte que los escribiera sin el aviso
    pasaría cualquier caso que sólo midiera el valor de retorno.

    **La categoría del aviso NO es uniforme, y eso también se mide.** Cuatro
    de los diez pasan ``DeprecationWarning`` explícito —``insert_missing``,
    ``patch``, ``patch_and_set`` y ``get_records_different_from``— y los otros
    seis llaman a ``warnings.warn`` pelado, que en Python es ``UserWarning``.
    El porte lo replica verbatim porque la fidelidad manda, así que cada caso
    exige **su** categoría: pedir ``DeprecationWarning`` a los seis pelados
    fallaría, y pedir ``Warning`` a secas no distinguiría los dos grupos —
    sería un verde que no discrimina.
    """

    def test_insert_missing_warns(self, open_transaction):
        with pytest.warns(DeprecationWarning):
            open_transaction.cache.insert_missing(
                [CacheFacadeProbe(pk=1)], field_of('source'), [1])

    def test_patch_and_set_warns(self, open_transaction):
        with pytest.warns(DeprecationWarning):
            open_transaction.cache.patch_and_set(
                CacheFacadeProbe(pk=1), field_of('source'), 1)

    def test_get_until_miss_warns(self, open_transaction):
        with pytest.warns(UserWarning):
            open_transaction.cache.get_until_miss(
                [CacheFacadeProbe(pk=1)], field_of('source'))

    def test_get_dirty_fields_warns(self, open_transaction):
        with pytest.warns(UserWarning):
            open_transaction.cache.get_dirty_fields()

    def test_has_dirty_fields_warns(self, open_transaction):
        with pytest.warns(UserWarning):
            open_transaction.cache.has_dirty_fields(
                [CacheFacadeProbe(pk=1)], [field_of('source')])

    def test_clear_dirty_field_warns(self, open_transaction):
        with pytest.warns(UserWarning):
            open_transaction.cache.clear_dirty_field(field_of('source'))


class TestTheDeprecatedSurfaceStillAnswers:
    """Obsoleto no es ausente: los que devuelven valor lo siguen devolviendo."""

    def test_get_until_miss_stops_at_the_first_gap(self, open_transaction):
        field = field_of('source')
        open_transaction.cache.set(CacheFacadeProbe(pk=1), field, 10)
        records = [CacheFacadeProbe(pk=1), CacheFacadeProbe(pk=2),
                   CacheFacadeProbe(pk=3)]
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            assert open_transaction.cache.get_until_miss(records, field) == [10]

    def test_insert_missing_does_not_overwrite(self, open_transaction):
        field = field_of('source')
        open_transaction.cache.set(CacheFacadeProbe(pk=1), field, 10)
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            open_transaction.cache.insert_missing(
                [CacheFacadeProbe(pk=1), CacheFacadeProbe(pk=2)], field, [99, 20])
        assert open_transaction.cache.get(CacheFacadeProbe(pk=1), field) == 10
        assert open_transaction.cache.get(CacheFacadeProbe(pk=2), field) == 20

    def test_clear_dirty_field_returns_the_formerly_dirty_ids(
            self, open_transaction):
        field = field_of('source')
        open_transaction.cache.set(CacheFacadeProbe(pk=1), field, 1, dirty=True)
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            assert 1 in open_transaction.cache.clear_dirty_field(field)
        assert not open_transaction.field_dirty.get(field)

    def test_has_dirty_fields_sees_the_marked_one(self, open_transaction):
        field = field_of('source')
        open_transaction.cache.set(CacheFacadeProbe(pk=1), field, 1, dirty=True)
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            assert open_transaction.cache.has_dirty_fields(
                [CacheFacadeProbe(pk=1)], [field])
            assert not open_transaction.cache.has_dirty_fields(
                [CacheFacadeProbe(pk=2)], [field])


@pytest.mark.django_db
class TestTheMethodsThatReturnRows:
    """Los cuatro que devuelven filas — aquí un ``QuerySet``, no un recordset.

    Se miden contra ``res.partner`` porque evaluarlos toca la base: la sonda
    ``managed = False`` no tiene tabla, y un caso que no evaluara el
    ``QuerySet`` no distinguiría un ``browse`` correcto de uno que filtra por
    los ids equivocados.
    """

    @pytest.fixture
    def two_partners(self):
        return (ResPartner.objects.create(name='Alfa'),
                ResPartner.objects.create(name='Bravo'))

    def _partner_field(self):
        return ResPartner, ResPartner._meta.get_field('comment')

    def test_get_records_returns_the_rows_with_a_value(
            self, open_transaction, two_partners):
        alpha, _bravo = two_partners
        model, field = self._partner_field()
        open_transaction.cache.set(alpha, field, 'x')
        assert record_ids(open_transaction.cache.get_records(model, field)) == (alpha.pk,)

    def test_filtered_dirty_records_keeps_only_the_marked(
            self, open_transaction, two_partners):
        alpha, bravo = two_partners
        model, field = self._partner_field()
        open_transaction.cache.set(alpha, field, 'x', dirty=True)
        open_transaction.cache.set(bravo, field, 'y')
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            dirty_rows = open_transaction.cache.filtered_dirty_records(
                model.objects.filter(pk__in=[alpha.pk, bravo.pk]), field)
            clean_rows = open_transaction.cache.filtered_clean_records(
                model.objects.filter(pk__in=[alpha.pk, bravo.pk]), field)
        assert record_ids(dirty_rows) == (alpha.pk,)
        assert record_ids(clean_rows) == (bravo.pk,)

    def test_get_records_different_from_names_the_others(
            self, open_transaction, two_partners):
        """Delega en ``Field._filter_not_equal``, que #326 porta."""
        alpha, bravo = two_partners
        model, field = self._partner_field()
        open_transaction.cache.set(alpha, field, 'x')
        open_transaction.cache.set(bravo, field, 'y')
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            differing = open_transaction.cache.get_records_different_from(
                model.objects.filter(pk__in=[alpha.pk, bravo.pk]), field, 'x')
        assert record_ids(differing) == (bravo.pk,)


class TestTheRegistryIsTheModule:
    """La tercera divergencia: el mapa derivado vive en ``orm.registry``."""

    def test_the_context_map_is_the_one_of_the_module(self):
        assert registry.field_depends_context is not None

    def test_the_ambient_environment_answers_without_a_cursor(self):
        """La primera divergencia, medida: no hace falta ``model.env``."""
        assert ambient_env() is not None


@pytest.mark.django_db
class TestTheFieldWithoutAColumnAlsoLivesInTheCache:
    """Un campo sin columna es el que MÁS depende de la caché, no el que menos.

    En la fuente no hay dos clases: ``display_name`` es un ``Field`` con
    ``compute`` y sin ``store``, y su valor **sólo** existe en la caché de la
    transacción — no hay columna de donde releerlo. Por eso ``Cache`` lo trata
    igual que a cualquier otro y ``get_fields`` lo enumera.

    Aquí la separación en dos clases —``models.Field`` de Django y
    :class:`~orm.fields_nonstored.NonStored`— es divergencia de stack, no de
    contrato: el bloque de caché de ``src/orm/fields.py`` se instala sobre las
    dos. Sin eso, ``Cache.get_fields`` reventaba con ``AttributeError`` en el
    primer modelo que declarara uno, que son todos: ``display_name`` es
    universal en este árbol (tarea #134).

    Qué haría fallar a estos casos
    ==============================

    Retirar ``NonStored`` de la lista de instalación deja los cuatro en rojo
    con ``AttributeError: 'NonStored' object has no attribute '_get_cache'``.
    Y el último discrimina la otra mitad: si alguien le diera ``store=True`` a
    un campo sin columna, la marca de sucio empezaría a prender y el volcado
    intentaría escribir una columna que no existe.
    """

    def test_the_cache_holds_a_value_for_a_field_without_a_column(
            self, open_transaction):
        record = CacheFacadeProbe(pk=1)
        field = non_stored_fields(CacheFacadeProbe)['display_name']
        open_transaction.cache.set(record, field, 'Sonda')
        assert open_transaction.cache.get(record, field) == 'Sonda'

    def test_contains_sees_the_field_without_a_column(self, open_transaction):
        record = CacheFacadeProbe(pk=1)
        field = non_stored_fields(CacheFacadeProbe)['display_name']
        assert not open_transaction.cache.contains(record, field)
        open_transaction.cache.set(record, field, 'Sonda')
        assert open_transaction.cache.contains(record, field)

    def test_get_fields_enumerates_it_alongside_the_stored_one(
            self, open_transaction):
        """``get_fields`` recorre ``_fields``, que incluye los dos ejes."""
        record = CacheFacadeProbe(pk=1)
        open_transaction.cache.set(record, field_of('source'), 1)
        open_transaction.cache.set(
            record, non_stored_fields(CacheFacadeProbe)['display_name'], 'Sonda')
        names = {f.name for f in open_transaction.cache.get_fields(record)}
        assert names == {'source', 'display_name'}

    def test_it_never_becomes_dirty_even_when_asked(self, open_transaction):
        """``dirty=True`` sobre un campo sin columna es un no-op.

        ``_is_persisted`` (``src/orm/fields.py``) exige ``store`` **y**
        columna o tabla intermedia; un campo sin columna no tiene ninguna de
        las dos, así que nunca entra en ``field_dirty`` y el volcado no
        intenta escribirlo.
        """
        record = CacheFacadeProbe(pk=1)
        field = non_stored_fields(CacheFacadeProbe)['display_name']
        open_transaction.cache.set(record, field, 'Sonda', dirty=True)
        assert not open_transaction.field_dirty.get(field)
