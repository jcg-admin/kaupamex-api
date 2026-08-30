"""El protocolo de descripción de ``Field`` — ≙ ``odoo19c: :872-975``.

Es el bloque con que un campo se describe a su cliente. La fuente lo resuelve
con un convenio de nombres —``_description_<clave>``— y una tabla derivada por
``dir()``; aquí la derivación la hace un descriptor de clase porque
``__init_subclass__`` es una de las cuatro colisiones medidas con Django.

Cada clase de este archivo fija una pregunta distinta, y dos de ellas son
**controles que pueden fallar**: el de ``ArrayField`` reproduce el arranque que
el porte reventó, y el de la tabla derivada comprueba que una subclase con su
propio ``_description_*`` lo ve.
"""
from unittest import mock

from django.contrib.postgres.fields import ArrayField
from django.db import models

from orm import registry
from orm.environments import env
from orm.fields import _ComputedUnlessAssigned, _DerivedFromPrefix


class TestTheDerivedTable:
    """La tabla ``description_attrs`` que la fuente deriva en
    ``__init_subclass__`` y aquí un descriptor de clase."""

    def test_it_publishes_the_key_without_the_prefix(self):
        table = dict(models.Field.description_attrs)
        assert table['type'] == '_description_type'
        assert table['searchable'] == '_description_searchable'
        assert 'name' in table

    def test_the_related_table_uses_its_own_prefix(self):
        table = dict(models.Field.related_attrs)
        assert set(table) == {'comodel_name', 'string', 'help', 'groups',
                              'aggregator'}
        assert all(a.startswith('_related_') for a in table.values())

    def test_a_subclass_sees_its_own_entry(self):
        """El control que discrimina: la fuente deriva por subclase, no una
        sola vez. Si la derivación se hubiera hecho una vez sobre la base, la
        clave nueva no aparecería."""

        class FieldWithItsOwnKey(models.CharField):
            _description_invented_here = property(lambda self: 'value')

        assert 'invented_here' in dict(FieldWithItsOwnKey.description_attrs)
        assert 'invented_here' not in dict(models.Field.description_attrs)

    def test_the_table_is_cached_per_class(self):
        first = models.CharField.description_attrs
        assert models.CharField.description_attrs is first

    def test_asking_the_base_does_not_destroy_the_descriptor(self):
        """Control que puede fallar, y que falló: con el caché por
        ``setattr`` la primera consulta sobre ``models.Field`` sustituía al
        descriptor por la tupla, y desde entonces ninguna subclase derivaba la
        suya."""
        models.Field.description_attrs  # noqa: B018 — el acceso ES la prueba
        assert isinstance(models.Field.__dict__['description_attrs'],
                          _DerivedFromPrefix)

        class FieldAfterTheBaseWasAsked(models.CharField):
            _description_asked_later = property(lambda self: 'value')

        assert 'asked_later' in dict(FieldAfterTheBaseWasAsked.description_attrs)

    def test_the_descriptor_is_the_one_the_port_installs(self):
        assert isinstance(models.Field.__dict__['related_attrs'],
                          _DerivedFromPrefix)


class TestGetDescription:
    """``get_description`` — el diccionario que describe el campo."""

    def test_it_answers_with_the_declared_label(self):
        field = models.CharField(max_length=8, verbose_name='Etiqueta')
        field.set_attributes_from_name('some_field')
        assert field.get_description(env())['name'] == 'some_field'

    def test_a_none_value_yields_no_key(self):
        """La clave ausente y la clave con ``None`` significan cosas distintas
        para el cliente, y la fuente elige la primera."""
        field = models.CharField(max_length=8)
        field.set_attributes_from_name('some_field')
        description = field.get_description(env())
        assert 'groups' not in description
        assert field.groups is None

    def test_it_honours_the_requested_subset(self):
        field = models.CharField(max_length=8)
        field.set_attributes_from_name('some_field')
        description = field.get_description(env(), attributes=['name'])
        assert set(description) == {'name'}

    def test_the_callable_ones_receive_the_environment(self):
        """``_description_sortable`` es un método, no una property: la fuente
        lo llama con el entorno. Sin la llamada, el valor publicado sería el
        método mismo."""
        field = models.CharField(max_length=8)
        field.set_attributes_from_name('some_field')
        assert field.get_description(env())['sortable'] is True


class TestTheIndividualAnswers:

    def test_searchable_is_the_disjunction_of_the_source(self):
        field = models.CharField(max_length=8)
        assert field._description_searchable is True
        field.store = False
        assert field._description_searchable is False
        field.search = lambda records, operator, value: []
        assert field._description_searchable is True

    def test_is_editable_is_not_djangos_editable(self):
        """Los dos nombres suenan igual y gobiernan cosas distintas: el de
        Django decide si el campo entra en un ``ModelForm``; el de la fuente,
        si la vista lo deja editar."""
        field = models.CharField(max_length=8, editable=False)
        assert field.editable is False
        assert field.is_editable() is True
        field.readonly = True
        assert field.is_editable() is False

    def test_column_type_turns_jsonb_when_the_value_is_a_map(self):
        field = models.CharField(max_length=8)
        assert field.column_type is None
        field.company_dependent = True
        assert field.column_type == ('jsonb', 'jsonb')
        field.company_dependent = False
        field.translate = True
        assert field.column_type == ('jsonb', 'jsonb')

    def test_base_field_walks_the_inheritance(self):
        base = models.CharField(max_length=8)
        derived = models.CharField(max_length=8)
        derived.inherited_field = base
        assert derived.base_field is base
        assert base.base_field is base


class TestTheArrayFieldCollision:
    """Control positivo REAL del árbol, no fabricado.

    ``ArrayField.__init__`` asigna ``self.base_field`` con otro significado —el
    campo de los elementos— y hereda de ``models.Field``. Con ``base_field``
    instalado como ``property``, esta asignación aborta con ``property of
    'ArrayField' object has no setter`` y con ella el arranque de Django
    entero. Es lo que ocurrió al portarlo, y lo que este caso impide que
    vuelva a ocurrir en silencio.
    """

    def test_an_array_field_keeps_its_own_meaning(self):
        array = ArrayField(models.TextField())
        assert isinstance(array.base_field, models.TextField)

    def test_the_descriptor_is_not_a_data_descriptor(self):
        """La distinción que hace posible lo anterior: sin ``__set__``, el
        ``__dict__`` de la instancia gana."""
        descriptor = models.Field.__dict__['base_field']
        assert isinstance(descriptor, _ComputedUnlessAssigned)
        assert not hasattr(descriptor, '__set__')


class TestFieldDepends:
    """``registry.field_depends`` — el mapa que ``_description_depends``
    consulta, derivado de ``@api.depends`` en vez de poblado por un setup."""

    def test_a_field_without_declarations_yields_the_empty_tuple(self):
        """El contrato de ``Collector`` en su lado de lectura: nunca
        ``KeyError``. ``_description_depends`` lo consulta para TODO campo."""
        assert registry.field_depends[models.CharField(max_length=8)] == ()

    def test_it_derives_from_the_marker_the_decorator_leaves(self):
        """Ejercita ``_build``, no un ``_table`` puesto a mano: el mapa tiene
        que ENCONTRAR la declaración recorriendo los modelos."""
        field = models.CharField(max_length=8)
        field._depends = ('partner_id.name', 'amount')

        class ModelWithOneField:
            class _meta:
                @staticmethod
                def get_fields():
                    return [field]

        collector = registry._DerivedCollector('_depends')
        with mock.patch.object(registry.apps, 'get_models',
                               return_value=[ModelWithOneField]):
            assert collector[field] == ('partner_id.name', 'amount')

    def test_it_follows_compute_to_the_decorated_method(self):
        """La segunda vía de derivación: el campo no lleva el marcador, lo
        lleva el método que ``compute`` nombra. Sin esta rama el mapa sería
        ciego a todo campo calculado, que son justamente los que dependen."""
        field = models.CharField(max_length=8)
        field.compute = '_compute_total'

        class ModelWithAComputedField:
            @staticmethod
            def _compute_total(records):
                return None

            class _meta:
                @staticmethod
                def get_fields():
                    return [field]

        ModelWithAComputedField._compute_total._depends = ('line_ids.amount',)
        collector = registry._DerivedCollector('_depends')
        with mock.patch.object(registry.apps, 'get_models',
                               return_value=[ModelWithAComputedField]):
            assert collector[field] == ('line_ids.amount',)

    def test_clearing_forces_a_new_derivation(self):
        collector = registry._DerivedCollector('_depends')
        collector._table = {'sentinel': ('value',)}
        collector.clear()
        assert collector._table is None

    def test_the_description_publishes_the_empty_tuple_not_nothing(self):
        """La tupla vacía NO es ``None``, así que la clave SÍ aparece. Es la
        distinción que ``get_description`` hace al omitir sólo el ``None``:
        «no depende de nada» y «no se sabe» son respuestas distintas.
        """
        field = models.CharField(max_length=8)
        field.set_attributes_from_name('some_field')
        description = field.get_description(env())
        assert 'depends' in description
        assert description['depends'] == ()
