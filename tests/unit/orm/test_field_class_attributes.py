"""Los atributos de clase de campo que la fuente declara por clase concreta.

``odoo19c: odoo/orm/fields_misc.py``, ``fields_numeric.py``,
``fields_binary.py``, ``fields_properties.py``, ``fields_selection.py`` y
``fields_textual.py`` declaran cada uno el suyo; aquí los cuelga
``orm/fields.py`` de la clase de Django que recibe ese trasplante.

**Por qué existe este archivo.** El bucle de 66 atributos ponía el defecto de
``Field`` en ``models.Field`` y nada más, así que toda clase concreta respondía
el defecto: un ``AutoField`` decía ``readonly=False`` donde la fuente dice
``True``, y ``column_type`` valía ``None`` para casi toda columna del árbol.
El gate ``scripts/check_field_class_attributes.py`` lo mide; estas pruebas
fijan la **conducta** que se corrige, que es lo que el gate no ve.

Los lectores no son hipotéticos —se midieron antes de tocar nada—: viven en
``src/orm/fields.py`` y son ``is_editable``, ``_description_string``,
``_description_aggregator`` y la ``property`` ``column_type``.
"""
from django.contrib.contenttypes.fields import GenericForeignKey
from django.db import models

from orm.fields import type_for


class TestThePrimaryKeyAnswersLikeTheSource:
    """``Id`` de la fuente (``fields_misc.py:89-95``) declara seis atributos.

    Las tres clases de clave automática de Django cuelgan del ``Field`` base y
    heredaban su defecto: ``AutoFieldMeta.__subclasscheck__`` hace que
    ``issubclass`` mienta, pero la **resolución de atributo** sigue el MRO, que
    es donde ``Id`` no está.
    """

    AUTO_PK_CLASSES = (models.AutoField, models.BigAutoField,
                       models.SmallAutoField)

    def test_it_is_readonly(self):
        """``readonly = True`` (``:94``). Su lector es ``is_editable``."""
        for field_class in self.AUTO_PK_CLASSES:
            assert field_class.readonly is True, field_class.__name__

    def test_the_reader_of_readonly_says_it_is_not_editable(self):
        """El control de conducta: ``is_editable`` devuelve ``not readonly``.

        Antes de este porte la clave primaria de **todo** modelo se declaraba
        editable en una vista.
        """
        for field_class in self.AUTO_PK_CLASSES:
            assert field_class(primary_key=True).is_editable() is False

    def test_its_label_is_the_one_of_the_source(self):
        """``string = 'ID'`` (``:93``). Su lector es ``_description_string``."""
        for field_class in self.AUTO_PK_CLASSES:
            assert field_class.string == 'ID', field_class.__name__

    def test_it_is_not_prefetched(self):
        """``prefetch = False`` (``:95``)."""
        for field_class in self.AUTO_PK_CLASSES:
            assert field_class.prefetch is False, field_class.__name__

    def test_its_column_type_is_declared_whole(self):
        """``column_type = ('int4', 'int4')`` (``:92``) — la fuente lo declara
        en el atributo **público**, saltándose ``_column_type``."""
        for field_class in self.AUTO_PK_CLASSES:
            assert field_class(primary_key=True).column_type == ('int4', 'int4')


class TestTheNumericAggregate:
    """``aggregator = 'sum'`` en ``Integer``, ``Float`` y ``Monetary``
    (``fields_numeric.py:21``, ``:107``, ``:197``)."""

    def test_the_three_numeric_families_aggregate_with_sum(self):
        assert models.IntegerField.aggregator == 'sum'
        assert models.FloatField.aggregator == 'sum'
        assert models.DecimalField.aggregator == 'sum'

    def test_a_non_numeric_field_does_not_aggregate(self):
        """El control que discrimina: si el atributo se pusiera en el ``Field``
        base en vez de por clase, esto también diría ``'sum'``."""
        assert models.CharField.aggregator is None
        assert models.BooleanField.aggregator is None


class TestTheColumnTypeOfEachFamily:
    """``_column_type`` — la fuente lo declara literal en once clases y como
    ``property`` en dos (``Char`` y ``Float``), porque ahí depende de la
    instancia."""

    def test_the_literal_families_answer_their_tuple(self):
        assert models.BooleanField().column_type == ('bool', 'bool')
        assert models.IntegerField().column_type == ('int4', 'int4')
        assert models.DecimalField().column_type == ('numeric', 'numeric')
        assert models.JSONField().column_type == ('jsonb', 'jsonb')
        assert models.TextField().column_type == ('text', 'text')

    def test_char_derives_its_size_from_the_instance(self):
        """``Char._column_type`` (``fields_textual.py:494-496``) es
        ``('varchar', pg_varchar(self.size))``. El equivalente de ``size`` en
        este stack es ``max_length``.
        """
        assert models.CharField(max_length=64).column_type == \
            ('varchar', 'VARCHAR(64)')
        assert models.CharField().column_type == ('varchar', 'VARCHAR')

    def test_float_without_declared_digits_is_a_double(self):
        """``Float._column_type`` (``fields_numeric.py:125-133``) devuelve
        ``('numeric','numeric')`` con dígitos declarados y ``('float8',
        'float8')`` sin ellos. Aquí la rama de dígitos **es otra clase**
        —``DecimalField``—, así que ``FloatField`` sólo puede ser la otra.
        """
        assert models.FloatField().column_type == ('float8', 'float8')

    def test_a_temporal_field_keeps_the_one_it_already_had(self):
        """Control de no-regresión: ``fields_temporal._attach_base_date`` ya lo
        instalaba antes de este porte."""
        assert models.DateField().column_type == ('date', 'date')
        assert models.DateTimeField().column_type == ('timestamp', 'timestamp')


class TestTheReadersThatConsumeThem:
    """Los cuatro lectores medidos en ``src/orm/fields.py`` antes de portar."""

    def test_the_aggregator_reader_offers_the_sum_of_a_stored_column(self):
        """``_description_aggregator`` (``:1404-1411``) devuelve el agregado
        cuando el campo tiene columna y se guarda."""
        field = models.IntegerField()
        field.set_attributes_from_name('color')
        assert field._description_aggregator(None) == 'sum'

    def test_the_type_of_a_char_still_discriminates_by_choices(self):
        """Control de no-regresión del vecino: ``type`` sigue siendo una
        ``property`` que distingue ``Char`` de ``Selection``, y el
        ``column_type`` de las dos coincide por serlo de la misma clase."""
        assert type_for(models.CharField(max_length=8)) == 'char'
        assert type_for(models.CharField(max_length=8,
                                         choices=[('a', 'A')])) == 'selection'

class TestTheColumnTypeOfTheTwoTreeDivergences:
    """``_column_type`` donde el árbol de Django no es el de la fuente.

    Los dos casos los hizo visibles la tarea #248: hasta entonces
    ``_column_type`` estaba excluido del gate **entero**, por dos clases que la
    fuente resuelve con ``property``. Al excluir por par en vez de por
    atributo, once contrapartes pasaron a medirse y dos mentían.
    """

    def test_the_primary_key_does_not_inherit_the_integer_column(self):
        """``Field._column_type = None`` (``odoo19c: :259``) y la fuente
        declara ``class Id(Field)``.

        Aquí las tres claves automáticas descienden de ``IntegerField``, que sí
        recibe el ``('int4','int4')`` de ``Integer``. Es la misma divergencia de
        árbol de :ref:`h-api-970`, y sin declararlo la clave primaria respondía
        un ``_column_type`` que su contraparte no tiene.
        """
        for field_class in (models.AutoField, models.BigAutoField,
                            models.SmallAutoField):
            assert field_class._column_type is None, field_class.__name__
        #: Lo que sí publica el tipo de la columna de la clave — ``:781-783``
        #: lo lee a través de ``column_type``, no de ``_column_type``.
        assert models.AutoField.column_type == ('int4', 'int4')

    def test_the_generic_reference_keeps_the_integer_column(self):
        """``Many2oneReference(Integer)`` guarda el id crudo del apuntado.

        ``GenericForeignKey`` no desciende de ``IntegerField``, así que sin
        declararlo respondía ``None``: la columna que la fuente declara
        desaparecía del contrato.
        """
        assert GenericForeignKey._column_type == ('int4', 'int4')
