"""``_update_inverse`` y su familia — el otro lado de la relación en caché (#326).

Cuando se escribe un lado de una relación, el lado **contrario** que ya vive en
la caché de la transacción queda obsoleto. ``_update_inverse`` es quien lo pone
al día, y su único consumidor es ``Cache.patch``
(``odoo19c: odoo/orm/environments.py:906``). La fuente lo declara en tres
niveles y este árbol porta los tres:

=================================  ==========================================
``_Relational._update_inverse``    ``:81`` — el contrato: ``NotImplementedError``
``Many2one._update_inverse``       ``:322-324`` — convierte y escribe la caché
``_RelationalMulti._update_inverse``  ``:564-573`` — suma el id, o lo aparca
=================================  ==========================================

El veredicto por símbolo, con el criterio de las dos categorías:

===========================  ==============================================
El stack lo trae hecho       nada. Django no tiene caché por transacción, así
                             que ningún método de esta familia adapta algo
                             suyo.
El stack tiene con qué       la familia entera: se escribe sobre las
construirlo                  primitivas que este árbol ya construyó —el mapa
                             por campo de ``Transaction``, ``SENTINEL`` y
                             ``unique`` de ``tools.misc``.
===========================  ==============================================

Las cuatro divergencias de mecanismo que estos casos fijan
==========================================================

1. **El entorno es ambiental** — ``orm.environments.env()`` en vez de
   ``records.env``.
2. **No hay recordset** — ``records._ids`` es :func:`~orm.utils.record_ids` y
   ``record.id`` es :func:`~orm.fields_relational.single_record_id`.
3. **El registro es un módulo** — el campo conoce su ``related_model``, así que
   no hace falta ``model.env[self.comodel_name]``.
4. **``browse`` es una consulta.** La fuente envuelve el id con
   ``comodel.browse(new_id)`` sólo para darle a ``_update_inverse`` algo con
   ``.id``, y allá eso no consulta nada. Aquí un ``NewId`` no tiene fila que
   traer: el envoltorio volvería vacío y el id se perdería **en silencio**. Por
   eso ``Cache.patch`` lo pasa crudo y :func:`single_record_id` lo normaliza.

Qué haría fallar a estos casos
==============================

El control que discrimina la cuarta divergencia es
``test_a_new_id_survives_the_round_trip_through_the_cache``: si alguien
"corrigiera" ``Cache.patch`` para volver a envolver el id en un ``browse``, el
valor llegaría vacío y el caso caería. Un caso que sólo comprobara *"patch no
revienta"* sería verde con las dos versiones — el verde que no discrimina.

Y la rama ``dict`` de ``convert_to_cache`` se mide por su **excepción**, no por
su ausencia: levanta ``NotImplementedError`` con el número de su sucesor
dentro, así que el día que la tarea #327 construya ``BaseModel.new`` el caso
cae y obliga a portar la rama en vez de dejarla olvidada.
"""
import itertools

import pytest
from django.db import models as django_models
from django.db.models.fields.related import RelatedField

import fields
from addons.base.models.res_partner import ResPartner
from orm.environments import transaction_scope
from orm.fields_relational import single_record_id
from orm.identifiers import NewId
from tools.misc import SENTINEL, unique


class InverseProbeParent(django_models.Model):
    """El lado *uno* de las dos relaciones que esta familia gobierna."""

    _name = 'orm.inverse.probe.parent'

    name = fields.Char('Name', size=64)

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'orm_inverse_probe_parent'


class InverseProbeChild(django_models.Model):
    """El lado *muchos*: una FK y un M2M contra el mismo modelo."""

    _name = 'orm.inverse.probe.child'

    parent = django_models.ForeignKey(
        InverseProbeParent, on_delete=django_models.CASCADE,
        related_name='children', null=True, db_constraint=False)
    tags = django_models.ManyToManyField(
        InverseProbeParent, related_name='tagged', db_constraint=False)

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'orm_inverse_probe_child'


def fk_field():
    return InverseProbeChild._meta.get_field('parent')


def m2m_field():
    return InverseProbeChild._meta.get_field('tags')


@pytest.fixture
def open_transaction():
    """Cada caso corre en su propia transacción del ORM, como la fuente."""
    with transaction_scope() as tx:
        yield tx


class TestTheSingleRecordIdIsTheAdaptationOfRecordId:
    """:func:`single_record_id` — ≙ ``Id.__get__`` (``:103-114``)."""

    def test_the_empty_set_is_false(self):
        """Vacío devuelve ``False``, no ``None``: es lo que la fuente escribe."""
        assert single_record_id([]) is False

    def test_one_row_gives_its_id(self):
        """Un iterable de un elemento — la forma que
        :func:`~orm.utils.record_ids` admite sin instanciar el modelo."""
        assert single_record_id([7]) == 7

    def test_more_than_one_row_is_a_programming_error(self):
        """*"Expected singleton"* — la fuente levanta, y aquí también."""
        with pytest.raises(ValueError) as failure:
            single_record_id([7, 8])
        assert 'singleton' in str(failure.value)

    def test_a_bare_int_travels_raw(self):
        """La divergencia 4: el id llega suelto porque ``browse`` consulta."""
        assert single_record_id(7) == 7

    def test_a_bare_new_id_travels_raw_too(self):
        new_id = NewId()
        assert single_record_id(new_id) is new_id


class TestTheGenericContractRefuses:
    """``_Relational._update_inverse`` (``:81``) declara y delega."""

    def test_the_base_relational_raises_not_implemented(self):
        """Se porta el ``raise`` verbatim: un tipo relacional nuevo sin su
        implementación tiene que ser observable, no heredar la del vecino."""
        with pytest.raises(NotImplementedError):
            RelatedField._update_inverse(fk_field(), [], 1)

    def test_every_class_got_its_own_implementation(self):
        """Y las tres subclases lo tienen, cada una la suya."""
        assert (django_models.ForeignKey._update_inverse.__name__
                == '_many2one_update_inverse')
        assert (django_models.ManyToManyField._update_inverse.__name__
                == '_relational_multi_update_inverse')
        assert (django_models.ManyToManyField._update_cache.__name__
                == '_relational_multi_update_cache')


class TestTheMany2oneConvertsToTheCacheFormat:
    """``Many2one.convert_to_cache`` (``:328-351``) — el formato es id o ``None``."""

    def test_an_int_is_the_id_itself(self):
        assert fk_field().convert_to_cache(7, None) == 7

    def test_a_new_id_is_the_id_itself(self):
        new_id = NewId()
        assert fk_field().convert_to_cache(new_id, None) is new_id

    @pytest.mark.django_db
    def test_a_model_instance_gives_its_pk(self):
        parent = InverseProbeParent(pk=11)
        assert fk_field().convert_to_cache(parent, None) == 11

    @pytest.mark.django_db
    def test_a_queryset_of_the_wrong_model_is_refused(self):
        """``validate`` compara el modelo — con :func:`~orm.utils.model_of`,
        que es la vuelta de ``value._name`` de la fuente."""
        ResPartner.objects.create(name='Ajeno')
        with pytest.raises(ValueError):
            fk_field().convert_to_cache(ResPartner.objects.all(), None)

    @pytest.mark.django_db
    def test_the_wrong_model_passes_when_validation_is_off(self):
        """``validate=False`` es la vía por la que entra ``_update_inverse``."""
        foreign = ResPartner.objects.create(name='Ajeno')
        assert fk_field().convert_to_cache(
            ResPartner.objects.filter(pk=foreign.pk), None, validate=False) == foreign.pk

    def test_a_pair_gives_its_first_element(self):
        """El par ``(id, nombre)`` que la fuente admite."""
        assert fk_field().convert_to_cache((5, 'Cinco'), None) == 5

    def test_an_empty_tuple_is_none(self):
        assert fk_field().convert_to_cache((), None) is None

    def test_anything_else_is_none(self):
        assert fk_field().convert_to_cache('cinco', None) is None
        assert fk_field().convert_to_cache(None, None) is None

    def test_a_dict_declares_its_blockage_and_names_its_successor(self):
        """La rama que la fuente resuelve con ``comodel.new()``.

        No se emite media mecánica: portar sólo el ``NewId`` y tirar las demás
        claves del ``dict`` sería el conteo generoso que
        ``porte-completo-no-parcial`` prohíbe. El bloqueo lleva su sucesor
        dentro, y ese número es lo que hace caer el caso cuando se cierre.
        """
        with pytest.raises(NotImplementedError) as failure:
            fk_field().convert_to_cache({'name': 'Nuevo'}, None)
        assert '#327' in str(failure.value)

    @pytest.mark.django_db
    def test_delegation_wraps_the_id_when_every_row_is_new(self):
        """La guarda que da sentido a ``delegate`` (``:248``)."""
        field = fk_field()
        field.delegate = True
        try:
            wrapped = field.convert_to_cache(7, [InverseProbeChild()])
            assert isinstance(wrapped, NewId)
            assert wrapped.origin == 7
        finally:
            field.delegate = False

    @pytest.mark.django_db
    def test_delegation_leaves_the_id_alone_when_a_row_is_real(self):
        """El control de la guarda: con una fila guardada, el id no se envuelve."""
        field = fk_field()
        field.delegate = True
        try:
            assert field.convert_to_cache(7, [InverseProbeChild(pk=3)]) == 7
        finally:
            field.delegate = False


@pytest.mark.django_db
class TestTheMany2oneWritesTheCachePerRow:
    """``Many2one._update_inverse`` (``:322-324``)."""

    def test_it_converts_once_per_row(self, open_transaction):
        """Por fila y no en bloque: ``convert_to_cache`` consulta la propia
        fila para decidir si el id del padre delegado es nuevo."""
        field = fk_field()
        rows = [InverseProbeChild(pk=1), InverseProbeChild(pk=2)]
        field._update_inverse(rows, 9)
        assert open_transaction.cache.get(rows[0], field) == 9
        assert open_transaction.cache.get(rows[1], field) == 9

    def test_it_does_not_validate_the_model(self, open_transaction):
        """Entra con ``validate=False``: el valor viene del otro lado de la
        relación, que ya se validó al escribirse."""
        field = fk_field()
        foreign = ResPartner.objects.create(name='Ajeno')
        row = InverseProbeChild(pk=1)
        field._update_inverse([row], ResPartner.objects.filter(pk=foreign.pk))
        assert open_transaction.cache.get(row, field) == foreign.pk


@pytest.mark.django_db
class TestTheMultiAddsTheIdOrParksIt:
    """``_RelationalMulti._update_inverse`` (``:564-573``)."""

    def test_it_parks_the_id_when_the_row_has_no_cached_value(
            self, open_transaction):
        """Sin valor en caché el id no se puede sumar a nada: se aparca."""
        field = m2m_field()
        new_id = NewId()
        field._update_inverse([InverseProbeChild()], new_id)
        patches = open_transaction.field_data_patches[field]
        assert list(patches.values()) == [[new_id]]

    def test_it_adds_the_id_when_the_row_already_has_one(self, open_transaction):
        """Con valor en caché se suma, y sin repetir."""
        field = m2m_field()
        row = InverseProbeChild()
        first, second = NewId(), NewId()
        field._update_inverse([row], first)
        field._update_cache([row], ())          # drena el parche
        field._update_inverse([row], second)
        assert open_transaction.cache.get(row, field) == (first, second)

    def test_the_same_id_twice_appears_once(self, open_transaction):
        """``unique`` sobre el resultado — ≙ el de la fuente."""
        field = m2m_field()
        row = InverseProbeChild()
        new_id = NewId()
        field._update_inverse([row], new_id)
        field._update_cache([row], ())
        field._update_inverse([row], new_id)
        assert open_transaction.cache.get(row, field) == (new_id,)

    def test_a_real_id_is_refused(self, open_transaction):
        """La primera aserción de la fuente, portada verbatim: un id real se
        escribe por la vía normal, no parcheando la caché."""
        with pytest.raises(AssertionError):
            m2m_field()._update_inverse([InverseProbeChild()], 7)

    def test_a_saved_row_is_refused(self, open_transaction):
        """La segunda: sólo filas nuevas."""
        with pytest.raises(AssertionError):
            m2m_field()._update_inverse([InverseProbeChild(pk=3)], NewId())


@pytest.mark.django_db
class TestTheMultiDrainsThePendingPatches:
    """``_RelationalMulti._update_cache`` (``:576-586``)."""

    def test_the_parked_id_joins_the_value_being_written(self, open_transaction):
        field = m2m_field()
        row = InverseProbeChild()
        parked = NewId()
        field._update_inverse([row], parked)
        other = NewId()
        field._update_cache([row], (other,))
        assert open_transaction.cache.get(row, field) == (other, parked)

    def test_the_patch_is_consumed_only_once(self, open_transaction):
        field = m2m_field()
        row = InverseProbeChild()
        parked = NewId()
        field._update_inverse([row], parked)
        field._update_cache([row], ())
        field._update_cache([row], ())
        assert open_transaction.cache.get(row, field) == ()

    def test_without_patches_it_writes_the_value_as_is(self, open_transaction):
        """La rama de paso: sin parches pendientes delega en el genérico."""
        field = m2m_field()
        row = InverseProbeChild(pk=4)
        field._update_cache([row], (1, 2))
        assert open_transaction.cache.get(row, field) == (1, 2)


@pytest.mark.django_db
class TestTheCachePatchDeliversTheRawId:
    """``Cache.patch`` (``:906``) y la cuarta divergencia."""

    def test_a_new_id_survives_the_round_trip_through_the_cache(
            self, open_transaction):
        """El control que discrimina la divergencia 4.

        La fuente escribe ``field._update_inverse(records, comodel.browse(new_id))``.
        Con nuestro ``browse`` —que **consulta**— un ``NewId`` no tiene fila, el
        conjunto volvería vacío y :func:`single_record_id` daría ``False``: el
        id se perdería sin ruido. El caso lo hace observable.
        """
        field = m2m_field()
        row = InverseProbeChild()
        new_id = NewId()
        with pytest.warns(DeprecationWarning):
            open_transaction.cache.patch([row], field, new_id)
        patches = open_transaction.field_data_patches[field]
        assert list(patches.values()) == [[new_id]]


@pytest.mark.django_db
class TestTheFilterNotEqualUsesASentinel:
    """``Field._filter_not_equal`` (``:1577``) — el consumidor de ``SENTINEL``."""

    def test_a_row_without_a_cached_value_always_differs(self, open_transaction):
        """Sin valor en caché, la fila difiere de cualquier cosa.

        Se mide sobre ``ResPartner`` y no sobre las sondas de arriba porque
        ``_filter_not_equal`` devuelve :func:`~orm.utils.browse`, que **es una
        consulta**: exige una tabla real.
        """
        field = ResPartner._meta.get_field('name')
        partner = ResPartner.objects.create(name='Alfa')
        differing = field._filter_not_equal(partner, 'Alfa')
        assert [p.pk for p in differing] == [partner.pk]

    def test_a_row_with_the_same_cached_value_is_dropped(self, open_transaction):
        field = ResPartner._meta.get_field('name')
        partner = ResPartner.objects.create(name='Alfa')
        open_transaction.cache.set(partner, field, 'Alfa')
        assert list(field._filter_not_equal(partner, 'Alfa')) == []

    def test_a_cached_none_is_not_read_as_absent(self, open_transaction):
        """El caso que justifica el centinela, y el que lo discrimina.

        Con ``field_cache.get(id_, None)`` en vez de ``SENTINEL``, una fila
        cuyo valor en caché **es** ``None`` se leería igual que una fila sin
        valor: las dos «difieren» de todo. Aquí una fila con ``None`` en caché
        **no** difiere de ``None``, y ese es el único caso que separa las dos
        versiones.
        """
        field = ResPartner._meta.get_field('name')
        partner = ResPartner.objects.create(name='Alfa')
        open_transaction.cache.set(partner, field, None)
        assert list(field._filter_not_equal(partner, None)) == []
        assert SENTINEL is not None

    def test_a_queryset_is_the_other_admitted_form(self, open_transaction):
        """Instancia o ``QuerySet``, que son las dos formas en que este árbol
        representa un conjunto de filas."""
        field = ResPartner._meta.get_field('name')
        partner = ResPartner.objects.create(name='Alfa')
        rowset = ResPartner.objects.filter(pk=partner.pk)
        assert [p.pk for p in field._filter_not_equal(rowset, 'Otro')] == [partner.pk]

    def test_a_bare_list_is_refused(self, open_transaction):
        """Y una lista suelta **no**, a propósito.

        :func:`~orm.utils.model_of` rehúsa el iterable en vez de adivinar la
        clase por su primer elemento: adivinarla consumiría un generador, y
        devolver ``None`` ante lo desconocido convertiría el fallo en un
        ``AttributeError`` lejano. El caso fija esa frontera para que no se
        relaje por comodidad.
        """
        field = ResPartner._meta.get_field('name')
        partner = ResPartner.objects.create(name='Alfa')
        with pytest.raises(TypeError):
            field._filter_not_equal([partner], 'Alfa')


class TestTheUniquifierIsLazy:
    """``unique`` (``odoo19c: odoo/tools/misc.py:1213``) — el ayudante que
    ``_update_cache`` consume mientras drena."""

    def test_it_yields_before_consuming_the_rest(self):
        """La pereza es el motivo del porte, y esto la mide.

        ``list(dict.fromkeys(it))`` daría el mismo resultado y recorrería la
        secuencia entera antes de devolver nada; el contador de este caso lo
        distingue.
        """
        consumed = []

        def counting():
            for value in (1, 2, 3):
                consumed.append(value)
                yield value

        output = unique(counting())
        assert next(output) == 1
        assert consumed == [1]

    def test_it_drops_the_repetition_keeping_the_order(self):
        assert list(unique([3, 1, 3, 2, 1])) == [3, 1, 2]

    def test_it_chains_like_its_consumer_does(self):
        """La forma exacta con que ``_update_cache`` lo llama."""
        assert tuple(unique(itertools.chain((1, 2), (2, 3)))) == (1, 2, 3)

    def test_a_field_that_is_not_an_x2many_is_refused(self, open_transaction):
        """``assert isinstance(field, _RelationalMulti)`` (``:763``).

        La fuente lo declara con un import perezoso para romper su ciclo; aquí
        la clase es ``models.ManyToManyField`` y el import va al top. Sin la
        aserción, una FK caería en ``_many2one_update_inverse`` y escribiría la
        caché con un id **nuevo** sobre una fila cualquiera — corrupción
        silenciosa, que es lo que la aserción de la fuente impide.
        """
        with pytest.warns(DeprecationWarning), pytest.raises(AssertionError):
            open_transaction.cache.patch(
                [InverseProbeChild()], fk_field(), NewId())
