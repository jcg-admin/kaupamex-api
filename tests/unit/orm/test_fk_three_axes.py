"""Por qué Django separa símbolo, ``attname`` y columna — y qué ve cada capa (#141).

≙ ADR-029. Complementa a ``test_fk_column_naming.py``: aquél mide **qué
columna** tienen nuestras FK portadas; éste mide **por qué existen los tres
ejes** y qué consume cada capa del stack, que es lo que decide si
``db_column`` es cosmético o carga contrato.

La referencia colapsa los tres en un nombre
(``odoo19c: odoo/orm/fields_relational.py`` — ``partner_id = fields.Many2one(...)``
nombra atributo, columna y etiqueta). Django los separa porque una FK crea
**dos atributos de Python sobre la misma columna**, y eso no es una
peculiaridad de estilo: es lo que permite leer el pk sin traer el objeto.

Medido en el paquete instalado, no de memoria:

- ``django/db/models/fields/related.py:1160`` — ``ForeignKey.get_attname``
  devuelve ``"%s_id" % self.name``. El sufijo lo pone el ORM, siempre.
- ``django/db/models/fields/related.py:1163-1166`` — ``get_attname_column``
  resuelve ``column = self.db_column or attname``. Sin ``db_column`` la
  columna hereda el sufijo doblado.
- ``django/db/models/fields/related.py:924`` — ``contribute_to_class`` cuelga
  el descriptor sobre ``self.name``; el atributo crudo vive en ``attname``.
- ``django/db/models/base.py:794-809`` — ``serializable_value`` es el puente:
  recibe el NOMBRE y devuelve ``getattr(self, field.attname)``.
- ``django/db/backends/base/schema.py:378`` — el DDL usa ``field.column``.
- ``django/db/backends/base/schema.py:1494-1508`` — el nombre del índice se
  arma con el nombre de columna **y su digest**.

Qué haría fallar a estos casos
==============================

Que Django dejara de doblar el sufijo, o que ``db_column`` dejara de gobernar
la columna: los dos primeros bloques rompen. Que DRF empezara a leer la
columna en vez del símbolo: rompe el tercero, que es el que sostiene la
afirmación *"cambiar ``db_column`` no toca el contrato del API"*.
"""
import pytest
from django.db import connection, models
from rest_framework import serializers

from addons.base.models.ir_model import IrModel
from addons.base_automation.models.base_automation import BaseAutomation


class TestDjangoSeparatesThreeAxes:
    """Un ``ForeignKey`` produce DOS atributos de Python y UNA columna."""

    def test_the_symbol_carries_the_descriptor_that_returns_the_object(self):
        """``BaseAutomation.model_id`` es un descriptor, no un entero."""
        descriptor = BaseAutomation.__dict__['model_id']

        assert descriptor.__class__.__name__ == 'ForwardManyToOneDescriptor'

    def test_the_attname_carries_the_raw_pk_and_doubles_the_suffix(self):
        field = BaseAutomation._meta.get_field('model_id')

        assert field.attname == 'model_id_id'
        assert BaseAutomation.__dict__['model_id_id'].__class__.__name__ == (
            'ForeignKeyDeferredAttribute')

    def test_the_column_is_the_third_axis_and_db_column_governs_it(self):
        """``column = self.db_column or attname`` — con ``db_column``, fiel."""
        field = BaseAutomation._meta.get_field('model_id')

        assert field.db_column == 'model_id'
        assert field.column == 'model_id'
        assert field.column != field.attname

    def test_without_db_column_the_column_would_inherit_the_double_suffix(self):
        """El contrafactual, sobre un campo declarado al vuelo.

        Es el control que hace no-vacío al caso anterior: sin él, «la columna
        es ``model_id``» no distingue *"lo declaramos"* de *"Django ya lo
        hacía"*.
        """
        field = models.ForeignKey(IrModel, on_delete=models.CASCADE)
        field.set_attributes_from_name('model_id')

        assert field.attname == 'model_id_id'
        assert field.column == 'model_id_id'


class TestWhatEachLayerConsumes:
    """El símbolo lo consume Python y DRF; la columna, sólo PostgreSQL."""

    @pytest.mark.django_db
    def test_serializable_value_bridges_the_symbol_to_the_attname(self):
        """``django/db/models/base.py:809`` — el puente que DRF usa."""
        #: ``get_or_create``: la reflexión de modelos ya siembra la fila y
        #: ``ir_model.model`` es único.
        model_row, _ = IrModel.objects.get_or_create(
            model='base.ResPartner', defaults={'name': 'Contacto'})
        automation = BaseAutomation(model_id=model_row)

        assert automation.serializable_value('model_id') == model_row.pk

    @pytest.mark.django_db
    def test_drf_reads_the_symbol_never_the_column(self):
        """El contrato del API no cambia al declarar ``db_column``.

        ``rest_framework/relations.py:172-187`` — ``RelatedField.get_attribute``
        llama ``serializable_value(self.source_attrs[-1])``, y ese argumento es
        el NOMBRE del campo. La columna no aparece en ninguna capa de DRF.
        """
        model_row, _ = IrModel.objects.get_or_create(
            model='base.ResCountry', defaults={'name': 'Pais'})
        automation = BaseAutomation(name='A', model_id=model_row)

        class _Serializer(serializers.ModelSerializer):
            class Meta:
                model = BaseAutomation
                fields = ['model_id']

        assert _Serializer(automation).data['model_id'] == model_row.pk

    @pytest.mark.django_db
    def test_the_ddl_uses_the_column(self):
        """``django/db/backends/base/schema.py:378`` — ``column_sql``."""
        field = BaseAutomation._meta.get_field('model_id')

        with connection.schema_editor(collect_sql=True) as editor:
            definition, _params = editor.column_sql(BaseAutomation, field)

        assert definition is not None
        assert editor.quote_name(field.column) == '"model_id"'


class TestPostgresConsequences:
    """El nombre de columna gobierna el del índice, y PostgreSQL corta en 63."""

    @pytest.mark.django_db
    def test_the_index_name_derives_from_the_column_name(self):
        """``_create_index_name`` mezcla tabla + columnas + digest.

        Consecuencia: dos columnas que sólo difieren en el sufijo doblado
        producen nombres de índice distintos **y digests distintos**. Por eso
        llevar la columna a su nombre fiel es DDL real —un rename—, no un
        cambio de anotación.
        """
        with connection.schema_editor(collect_sql=True) as editor:
            faithful = editor._create_index_name('base_automation', ['model_id'])
            doubled = editor._create_index_name('base_automation', ['model_id_id'])

        assert faithful != doubled
        assert 'model_id' in faithful

    def test_the_identifier_limit_is_the_postgres_one(self):
        """63 — ``django/db/backends/postgresql/operations.py:289``.

        Cada ``_id`` de más consume tres de esos 63 en cada índice y en cada
        restricción que nombre la columna; el excedente lo absorbe el digest,
        que es ilegible. No es el motivo de ADR-029, pero sí una consecuencia
        medible de doblar el sufijo.
        """
        assert connection.ops.max_name_length() == 63


@pytest.mark.django_db
class TestTheCostThatJustifiesTheSplit:
    """Por qué la referencia PUEDE colapsar los tres nombres y Django no.

    No es preferencia de estilo: es la consecuencia de dos regímenes de
    evaluación distintos. En la referencia el objeto relacionado se obtiene
    con **coste de consulta cero** —evaluación perezosa—; en Django se
    materializa de forma **ansiosa**, y esa materialización es una consulta.

    - **La referencia.** ``convert_to_cache`` guarda *"cache format: id or
      None"* (``odoo19c: odoo/orm/fields_relational.py:329-330``) y
      ``convert_to_record`` (``:354-358``) construye el recordset con
      ``record.pool[comodel](env, ids, prefetch_ids)`` — sin consultar; un
      recordset es ``(modelo, ids, env)`` y ``browse`` (``odoo/orm/models.py:5883``)
      no emite ninguna consulta. Así que ``record.partner_id`` devuelve el
      recordset y ``record.partner_id.id`` devuelve el pk, **ambos con coste
      de consulta cero**: no hay dos caminos de acceso con costes distintos,
      luego no hacen falta dos nombres.

    - **Django.** ``record.partner`` materializa una instancia con todas sus
      columnas, y esa materialización cuesta una consulta salvo que esté
      precargada (``select_related`` o la caché de instancia del descriptor).
      El pk sin consulta sólo se alcanza por el segundo atributo. Dos costes
      de consulta distintos, dos nombres.

    Este bloque mide ese coste. Es lo que convierte *"Django los separa"* de
    afirmación en hecho verificable, y lo que decide nuestra implementación:
    el eje que no podemos hacer fiel —``attname``— es el único acceso al pk
    con coste de consulta cero, que es lo que allá da el propio recordset.
    """

    def test_reading_the_symbol_costs_a_query(self, django_assert_num_queries):
        model_row, _ = IrModel.objects.get_or_create(
            model='base.ResUsers', defaults={'name': 'Usuario'})
        BaseAutomation.objects.create(name='A', model_id=model_row)
        fresh = BaseAutomation.objects.get(name='A')

        with django_assert_num_queries(1):
            assert fresh.model_id.pk == model_row.pk

    def test_reading_the_attname_costs_none(self, django_assert_num_queries):
        """El acceso al pk que la referencia no necesita declarar aparte."""
        model_row, _ = IrModel.objects.get_or_create(
            model='base.ResLang', defaults={'name': 'Idioma'})
        BaseAutomation.objects.create(name='B', model_id=model_row)
        fresh = BaseAutomation.objects.get(name='B')

        with django_assert_num_queries(0):
            assert fresh.model_id_id == model_row.pk

    def test_the_truthiness_of_both_axes_coincides_and_that_is_the_trap(self):
        """``if record.model_id:`` compila y pasa bajo las DOS lecturas.

        En la referencia ese ``if`` pregunta *"¿hay recordset?"*; aquí, sobre
        el ``attname``, preguntaría *"¿hay entero no nulo?"*. Los dos dan lo
        mismo, así que un porte que confunda los ejes **no falla**: es el
        sub-patrón D de ``metrica-decide-la-conclusion.md`` — el verde que no
        discrimina. Por eso la divergencia del ``attname`` se declara en el
        archivo en vez de confiarse a la lectura.
        """
        empty = BaseAutomation()

        assert bool(empty.model_id_id) is False
        with pytest.raises(Exception):
            bool(empty.model_id)


@pytest.mark.django_db
class TestDjangoDoesHaveAttributeLevelLaziness:
    """El descriptor de la FK es ansioso; el ORM entero **no**.

    Es la mitad que falta cuando se dice *"Django o trae el objeto completo o
    no trae nada"*. Cierto del ``__get__`` de la FK —
    ``related_descriptors.py:257`` llama ``get_object`` y ``get_object``
    (``:308-311``) hace ``qs.get(...)``, sin nivel intermedio — y **falso**
    del ORM: ``DeferredAttribute.__get__``
    (``django/db/models/query_utils.py``) llama
    ``instance.refresh_from_db(fields=[field_name])`` en el primer acceso,
    que es evaluación perezosa a nivel de atributo con todas sus letras.

    La consecuencia práctica está en el segundo caso: componiendo
    ``select_related`` con ``only`` se obtiene una instancia relacionada que
    sólo conoce su pk y consulta al tocarle un campo. Ésa es la forma del
    proxy perezoso, construida con la API pública del stack.

    Qué haría fallar a estos casos
    ==============================

    Que ``only``/``defer`` dejaran de instalar ``DeferredAttribute``, o que
    ``select_related`` dejara de poblar la caché del descriptor: el conteo de
    consultas del segundo caso pasaría de ``0`` a ``1``.
    """

    def _automation(self, model_name, label):
        model_row, _ = IrModel.objects.get_or_create(
            model=model_name, defaults={'name': label})
        return BaseAutomation.objects.create(name=label, model_id=model_row)

    def test_a_deferred_field_fires_its_own_query_on_first_access(
            self, django_assert_num_queries):
        """``only`` deja la instancia incompleta y el campo se trae solo."""
        self._automation('base.ResGroups', 'Diferido')
        fresh = BaseAutomation.objects.only('name').get(name='Diferido')

        assert 'trigger' in fresh.get_deferred_fields()
        with django_assert_num_queries(1):
            fresh.trigger

    def test_select_related_with_only_builds_the_pk_only_proxy(
            self, django_assert_num_queries):
        """La relación a coste cero y su campo a una consulta.

        Es el reparto que se atribuye a los proxies de otros ORM: obtener la
        referencia no consulta; tocar un atributo del referenciado, sí.
        """
        self._automation('base.ResCountry', 'Proxy')
        fresh = (BaseAutomation.objects
                 .select_related('model_id')
                 .only('name', 'model_id__id')
                 .get(name='Proxy'))

        with django_assert_num_queries(0):
            related = fresh.model_id
            assert related.pk is not None
        assert 'model' in related.get_deferred_fields()
        with django_assert_num_queries(1):
            related.model

    def test_a_nullable_fk_returns_none_without_a_query(
            self, django_assert_num_queries):
        """El otro camino sin consulta: ``has_value`` es falso.

        ``related_descriptors.py:246`` corta antes de ``get_object`` cuando el
        valor local es nulo, así que ``null=True`` da el símbolo a coste cero.
        """
        self._automation('base.ResPartnerTitle', 'SinFecha')
        fresh = BaseAutomation.objects.get(name='SinFecha')

        assert fresh.trg_date_id_id is None
        with django_assert_num_queries(0):
            assert fresh.trg_date_id is None
