"""Contrato de la clase ``Selection`` — ``odoo19c:
odoo/orm/fields_selection.py:20-241``.

Oráculo literal leído del cuerpo de la referencia en ``odoo-tools@abe4040e``:

- ``type = 'selection'``, ``validate = True``, ``ondelete = None``
  (``:61-67``); ``selection`` es una lista de pares, un invocable o el nombre
  de un método, y ``_selection`` es el ``dict`` de la lista o ``None``
  (``:69-71``).
- ``convert_to_cache`` (``:228-236``): sin validar o sin lista devuelve
  ``value or None``; un valor de la lista pasa; el vacío es ``None``; otro
  valor levanta ``ValueError('Wrong value for …')``.
- ``convert_to_column`` (``:223-226``) valida sólo si ``self.validate``.
- ``get_values`` (``:216-221``) y ``_default_group_expand`` (``:212-214``)
  devuelven los valores; con invocable o nombre se calcula sobre el modelo.
- ``_description_selection`` (``:199-210``) fuerza claves y etiquetas a texto
  cuando la selección se calcula, y traduce la lista por
  ``ir.model.fields.get_field_selection``.
- ``convert_to_export`` (``:238-241``) da la etiqueta, o el valor.

Mutaciones que lo hacen caer: validar con ``validate=False`` (cae la de
columna); devolver el valor sin comprobarlo (cae la del rechazo); no llevar la
lista posicional a ``choices`` (cae la del consumidor ``website``); devolver la
ruta propia en ``deconstruct`` (cae la de migraciones).
"""
import pytest
from django.core.exceptions import ValidationError
from django.db import models

import fields
from addons.website.models.website import Website
from addons.website.models.website_rewrite import WebsiteRewrite

pytestmark = pytest.mark.integration

PAIRS = [('a', 'Alpha'), ('b', 'Beta')]


class _Records:
    """Un sujeto mínimo para ``determine``: método por nombre y contexto."""

    def __init__(self, log):
        self.log = log

    def with_context(self, **context):
        self.log.append(context)
        return self

    def _options(self):
        return [(1, 'One'), (2, 'Two')]


class _FieldsTable:
    @staticmethod
    def get_field_selection(model_name, field_name):
        return [('a', f'Alfa de {model_name}.{field_name}')]


class _Env(dict):
    pass


def _selection(*args, **kwargs):
    field = fields.Selection(*args, max_length=8, **kwargs)
    field.name = 'state'
    field.model_name = 'probe.model'
    return field


class TestSelectionIsAFieldClass:

    def test_the_declared_class_attributes(self):
        field = _selection(PAIRS)
        assert isinstance(field, models.CharField)
        assert type(field).__dict__['type'] == 'selection'
        assert bool(type(field).__dict__['validate']) is True
        assert bool(field.validate) is True
        assert type(field).ondelete is None

    def test_a_positional_list_is_the_selection_and_the_choices(self):
        field = _selection(PAIRS)
        assert field.selection == PAIRS
        assert field._selection == dict(PAIRS)
        assert list(field.choices) == PAIRS
        assert field.verbose_name in (None, 'state')

    def test_the_second_positional_is_the_label(self):
        field = _selection(PAIRS, 'State')
        assert field.verbose_name == 'State'

    def test_django_choices_are_the_selection_too(self):
        field = _selection(choices=PAIRS)
        assert field._selection == dict(PAIRS)

    def test_a_callable_or_a_name_has_no_static_dict(self):
        assert _selection(lambda records: PAIRS)._selection is None
        assert _selection('_options')._selection is None


class TestConversionsValidate:

    def test_cache_accepts_a_listed_value_and_empties(self):
        field = _selection(PAIRS, null=True)
        assert field.convert_to_cache('a', None) == 'a'
        assert field.convert_to_cache('', None) is None
        assert field.convert_to_cache(False, None) is None

    def test_cache_rejects_an_unlisted_value(self):
        with pytest.raises(ValueError, match='Wrong value for'):
            _selection(PAIRS).convert_to_cache('z', None)

    def test_cache_without_validation_passes_through(self):
        assert _selection(PAIRS).convert_to_cache('z', None, False) == 'z'
        assert _selection('_options').convert_to_cache('z', None) == 'z'

    def test_column_validates_only_when_the_field_does(self):
        field = _selection(PAIRS)
        with pytest.raises(ValueError):
            field.convert_to_column('z', None)
        field.validate = False
        assert not field.validate
        assert field.convert_to_column('z', None) == 'z'

    def test_an_empty_string_stays_empty_on_a_non_null_column(self):
        assert _selection(PAIRS).convert_to_cache('', None) == ''
        assert _selection(PAIRS).convert_to_column('', None) == ''
        assert _selection(PAIRS, null=True).convert_to_column('', None) is None

    def test_django_still_calls_validate_as_a_method(self):
        field = _selection(PAIRS)
        field.validate('a', None)
        with pytest.raises(ValidationError):
            field.validate('z', None)

    def test_export_gives_the_label(self):
        field = _selection(PAIRS)
        env = _Env({'ir.model.fields': _FieldsTable})
        record = type('R', (), {'env': env})()
        assert field.convert_to_export('a', record) == (
            'Alfa de probe.model.state')
        assert field.convert_to_export('b', record) == 'Beta'
        assert field.convert_to_export('', record) == ''


class TestValuesAndDescription:

    def test_values_of_a_list(self):
        assert _selection(PAIRS).get_values(_Env()) == ['a', 'b']

    def test_values_of_a_method_name_drop_the_language(self):
        log = []
        env = _Env({'probe.model': _Records(log)})
        assert _selection('_options').get_values(env) == [1, 2]
        assert log == [{'lang': None}]

    def test_group_expand_returns_the_values(self):
        field = _selection(PAIRS)
        records = type('R', (), {'env': _Env()})()
        assert field._default_group_expand(records, None, None) == ['a', 'b']

    def test_a_computed_description_is_text(self):
        env = _Env({'probe.model': _Records([])})
        assert _selection('_options')._description_selection(env) == [
            ('1', 'One'), ('2', 'Two')]

    def test_a_listed_description_is_translated(self):
        env = _Env({'ir.model.fields': _FieldsTable})
        assert _selection(PAIRS)._description_selection(env) == [
            ('a', 'Alfa de probe.model.state'), ('b', 'Beta')]


class TestMigrationsAndConsumers:

    def test_deconstruct_keeps_the_charfield_path(self):
        _name, path, _args, kwargs = _selection(PAIRS).deconstruct()
        assert path == 'django.db.models.CharField'
        assert 'selection' not in kwargs
        assert kwargs['choices'] == PAIRS

    def test_the_website_fields_declared_positionally_have_choices(self):
        signup = Website._meta.get_field('auth_signup_uninvited')
        assert signup._selection == {
            'b2b': 'On invitation', 'b2c': 'Free sign up'}
        assert not isinstance(signup.verbose_name, list)
        assert list(signup.choices) == [
            ('b2b', 'On invitation'), ('b2c', 'Free sign up')]
        redirect = WebsiteRewrite._meta.get_field('redirect_type')
        assert '301' in redirect._selection
