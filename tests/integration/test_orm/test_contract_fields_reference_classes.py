"""Contrato de ``Reference`` y ``Many2oneReference`` — ``odoo19c:
odoo/orm/fields_reference.py:13-118``.

Oráculo literal leído de la referencia en ``odoo-tools@abe4040e``:

- ``Reference(Selection)`` con ``type = 'reference'`` (``:20``); su columna
  guarda ``"modelo,id"``. ``convert_to_column`` es el de ``Field``, sin la
  validación de ``Selection`` (``:24-25``).
- ``convert_to_cache`` (``:27-40``): un registro de un modelo de la selección
  da ``"modelo,id"``; una cadena de un modelo de la selección pasa si la fila
  existe, y si no da ``None``; el vacío es ``None``; lo demás levanta
  ``ValueError('Wrong value for …')``.
- ``convert_to_record`` (``:42-46``), ``convert_to_read`` (``:48-49``) y
  ``convert_to_export`` (``:51-52``).
- ``Many2oneReference(Integer)`` con ``type = 'many2one_reference'``,
  ``model_field = None``, ``aggregator = None`` y los dos lectores de
  ``model_field`` (``:58-81``); ``convert_to_cache`` lleva un registro a su id
  (``:83-87``).

Mutaciones que lo hacen caer: validar en ``convert_to_column`` (cae la de
columna); aceptar un modelo fuera de la selección (cae la del rechazo); no
comprobar que la fila exista (cae la de la fila borrada); devolver la ruta
propia en el ``deconstruct`` de ``Many2oneReference`` (cae la del entero).
"""
import pytest
from django.db import models

import fields
from addons.base.models import ResCountry, ResPartner
from orm.fields import type_for
from orm.fields_reference import Many2oneReference, Reference
from orm.fields_selection import SelectionField

pytestmark = pytest.mark.integration

MODELS = [('res.partner', 'Contact'), ('res.country', 'Country')]


def _reference():
    field = fields.Reference(MODELS, max_length=64, null=True)
    field.name = 'target'
    field.model_name = 'probe.model'
    return field


@pytest.fixture
def partner(db):
    return ResPartner.objects.create(name='Referida')


class TestReferenceIsASelection:

    def test_the_class_and_its_type(self):
        field = _reference()
        assert isinstance(field, SelectionField)
        assert type(field) is Reference
        assert Reference.__dict__['type'] == 'reference'

    def test_its_column_keeps_the_charfield_path(self):
        _name, path, _args, _kwargs = _reference().deconstruct()
        assert path == 'django.db.models.CharField'


class TestReferenceConversions:

    def test_a_record_of_a_listed_model_becomes_model_comma_id(self, partner):
        assert _reference().convert_to_cache(partner, None) == (
            f'res.partner,{partner.pk}')

    def test_a_string_to_an_existing_row_passes(self, partner):
        value = f'res.partner,{partner.pk}'
        assert _reference().convert_to_cache(value, None) == value

    def test_a_string_to_a_deleted_row_is_none(self, partner):
        value = f'res.partner,{partner.pk}'
        ResPartner.objects.filter(pk=partner.pk).delete()
        assert _reference().convert_to_cache(value, None) is None

    def test_an_unlisted_model_is_refused(self, db):
        country = ResCountry.objects.first() or ResCountry.objects.create(
            name='Probelandia', code='ZZ')
        field = fields.Reference([('res.partner', 'Contact')], max_length=64)
        field.name, field.model_name = 'target', 'probe.model'
        with pytest.raises(ValueError, match='Wrong value for'):
            field.convert_to_cache(country, None)

    def test_empty_is_none(self):
        assert _reference().convert_to_cache(False, None) is None
        assert _reference().convert_to_cache('', None) is None

    def test_the_column_does_not_validate(self):
        assert _reference().convert_to_column('nope.model,7', None) == (
            'nope.model,7')

    def test_record_read_and_export(self, partner):
        field = _reference()
        record = field.convert_to_record(f'res.partner,{partner.pk}', None)
        assert record.pk == partner.pk
        assert field.convert_to_record(None, None) is None
        assert field.convert_to_read(partner, None) == (
            f'res.partner,{partner.pk}')
        assert field.convert_to_read(None, None) is False
        assert field.convert_to_export(partner, None) == partner.display_name
        assert field.convert_to_export(None, None) == ''


class TestMany2oneReference:

    def _field(self):
        field = fields.Many2oneReference(model_field='res_model', null=True)
        field.name = 'res_id'
        return field

    def test_the_class_attributes(self):
        field = self._field()
        assert isinstance(field, models.IntegerField)
        assert type(field) is Many2oneReference
        assert Many2oneReference.__dict__['type'] == 'many2one_reference'
        assert Many2oneReference.model_field is None
        assert Many2oneReference.aggregator is None
        assert field.model_field == 'res_model'
        assert field._related_model_field == 'res_model'
        assert field._description_model_field == 'res_model'

    def test_a_record_becomes_its_id(self, partner):
        assert self._field().convert_to_cache(partner, None) == partner.pk

    def test_its_column_keeps_the_integerfield_path(self):
        _name, path, _args, _kwargs = self._field().deconstruct()
        assert path == 'django.db.models.IntegerField'
        assert 'model_field' not in _kwargs


class TestTheTypeReachesTheRegistry:
    """``ir.model.fields`` lee el tipo con ``type_for``: tiene que decir lo
    mismo que el atributo de clase de la fuente."""

    def test_type_for_reads_the_class_type(self):
        assert type_for(_reference()) == 'reference'
        many = fields.Many2oneReference(model_field='res_model', null=True)
        assert type_for(many) == 'many2one_reference'
