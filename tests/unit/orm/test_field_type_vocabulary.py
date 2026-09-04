"""``Field.type`` — el vocabulario de la fuente sobre un campo de Django.

El registro de optimizadores de dominio despacha por ``field.type``
(``orm/domains.py:919``), y ``ir.model.fields.ttype_for`` publica el mismo
valor en el registro reflejado. Hasta este porte el atributo valia ``''`` en
todo campo salvo los dos temporales, asi que el despacho por tipo no podia
casar nunca: no fallaba, simplemente no encontraba a nadie.

Medido antes del porte (``scripts/workbench/field-type-vocabulary-*``):
**2 de 12** familias declaraban su ``type``; ``type_for`` ya sabia el de las
doce. Lo que faltaba no era el mapa, era cablearlo al atributo.
"""
import pytest
from django.db import models

from orm.domains import _OPTIMIZATIONS_FOR, OptimizationLevel
from orm.fields import type_for


class TestEveryFamilyPublishesItsType:
    """El vocabulario de la fuente, no la cadena vacia."""

    @pytest.mark.parametrize('field_class, expected', [
        (models.BooleanField, 'boolean'),
        (models.CharField, 'char'),
        (models.TextField, 'text'),
        (models.IntegerField, 'integer'),
        (models.FloatField, 'float'),
        (models.DecimalField, 'monetary'),
        (models.JSONField, 'json'),
        (models.BinaryField, 'binary'),
    ])
    def test_the_scalar_families(self, field_class, expected):
        assert field_class().type == expected

    @pytest.mark.parametrize('field_class, expected', [
        (models.EmailField, 'char'),
        (models.URLField, 'char'),
        (models.SlugField, 'char'),
        (models.UUIDField, 'char'),
        (models.PositiveIntegerField, 'integer'),
        (models.SmallIntegerField, 'integer'),
    ])
    def test_a_subclass_inherits_the_type_of_its_internal_type(
            self, field_class, expected):
        """``get_internal_type`` es quien decide, no el nombre de la clase."""
        assert field_class().type == expected

    def test_no_family_is_left_with_the_empty_string(self):
        families = [
            models.BooleanField, models.CharField, models.TextField,
            models.IntegerField, models.FloatField, models.DecimalField,
            models.DateField, models.DateTimeField, models.JSONField,
            models.BinaryField, models.EmailField, models.URLField,
        ]
        without_type = [c.__name__ for c in families if not c().type]
        assert without_type == [], without_type


class TestTheTemporalClassAttributeStillWins:
    """``fields_temporal`` declara ``type`` en la clase concreta, como la fuente.

    Un atributo llano de la subclase gana sobre una ``property`` de la base
    por resolucion de atributo. El porte no puede romper esa declaracion.
    """

    def test_date_keeps_its_declared_type(self):
        assert models.DateField().type == 'date'

    def test_datetime_keeps_its_declared_type(self):
        assert models.DateTimeField().type == 'datetime'

    def test_it_is_a_plain_class_attribute_not_the_property(self):
        assert 'type' in models.DateField.__dict__
        assert models.DateField.__dict__['type'] == 'date'


class TestSelectionIsDecidedByTheInstance:
    """Un ``CharField`` con ``choices`` **es** la selection de la fuente.

    Este es el caso que impide resolver ``type`` con un atributo de clase: dos
    instancias de la misma clase publican tipos distintos segun su estado.
    """

    def test_a_char_field_without_choices_is_char(self):
        assert models.CharField().type == 'char'

    def test_a_char_field_with_choices_is_selection(self):
        assert models.CharField(choices=[('a', 'A')]).type == 'selection'

    def test_the_two_are_the_same_class(self):
        assert type(models.CharField()) is type(
            models.CharField(choices=[('a', 'A')]))


class TestTheAttributeAgreesWithTypeFor:
    """``type`` y ``type_for`` no pueden divergir: uno delega en el otro."""

    @pytest.mark.parametrize('field', [
        models.BooleanField(),
        models.CharField(),
        models.CharField(choices=[('a', 'A')]),
        models.IntegerField(),
        models.JSONField(),
        models.DateField(),
        models.DateTimeField(),
    ])
    def test_they_agree(self, field):
        assert field.type == type_for(field)


class TestTheOptimizerRegistryCanDispatch:
    """El consumidor que motiva el porte: el despacho por tipo de campo.

    ``DomainCondition._optimize_step`` lee ``getattr(field, 'type', None)`` y
    busca esa clave en el registro. Con ``''`` la busqueda no casa con ninguna
    familia declarada, asi que la mitad por tipo del registro quedaba muerta.
    """

    def test_the_key_the_registry_would_look_up_is_the_vocabulary(self):
        field = models.BooleanField()
        assert getattr(field, 'type', None) == 'boolean'

    def test_an_empty_key_would_match_no_registered_family(self):
        registered = _OPTIMIZATIONS_FOR[OptimizationLevel.BASIC]
        assert '' not in registered


class TestRelationalIsTheDjangoPredicate:
    """``relational`` — el hermano de ``type``, con el mismo defecto de origen.

    La fuente lo declara una vez, en la base abstracta de los tres campos de
    relacion (``odoo19c: odoo/orm/fields_relational.py:35``). Aqui esa base es
    la de Django, que publica el mismo predicado como ``is_relation``.

    Instalado como valor llano valia ``False`` incluso en un ``ForeignKey``.
    """

    def test_a_scalar_field_is_not_relational(self):
        assert models.BooleanField().relational is False
        assert models.CharField().relational is False

    def test_a_foreign_key_is_relational(self):
        field = models.ForeignKey('self', on_delete=models.CASCADE)
        assert field.relational is True

    def test_a_many_to_many_is_relational(self):
        assert models.ManyToManyField('self').relational is True

    def test_it_agrees_with_the_django_predicate(self):
        for field in (models.BooleanField(), models.CharField(),
                      models.ForeignKey('self', on_delete=models.CASCADE),
                      models.ManyToManyField('self')):
            assert field.relational == field.is_relation, field
