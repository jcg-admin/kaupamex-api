"""Fusión de ``selection_add`` — ``odoo19c:
odoo/orm/fields_selection.py:93-177``.

Oráculo literal leído de la referencia en ``odoo-tools@abe4040e``:

- El docstring de la clase (``:30-35``) fija el orden:
  ``selection = [('a','A'),('b','B')]`` con
  ``selection_add = [('c','C'),('b',)]`` da ``[('a','A'),('c','C'),('b','B')]``
  — ``merge_sequences`` sobre las dos listas de claves (``:165-168``).
- Una etiqueta nueva gana sobre la anterior: ``values_add.get(key) or
  values[key]`` (``:166``); un singleton conserva la del campo ampliado.
- Ampliar una selección que no es lista se rechaza (``:124-125``).
- Todo valor nuevo sin política recibe ``'set null'`` (``:131-133``).

Aquí la fusión la hace ``extend_selection_choices``, y el campo ampliado tiene
que validar los valores nuevos al escribir.

Mutaciones que lo hacen caer: añadir al final en vez de fundir (cae la del
orden); ignorar la etiqueta nueva (cae la de la etiqueta); no actualizar la
selección de la clase (cae la de validación).
"""
import itertools

import pytest
from django.db import models
from django.test.utils import isolate_apps

import fields
from orm.model_classes import extend_selection_choices

pytestmark = pytest.mark.integration

_HOLDERS = itertools.count()


def _model(*args, **kwargs):
    with isolate_apps():
        meta = type('Meta', (), {'app_label': 'base'})
        return type(f'SelectionHolder{next(_HOLDERS)}', (models.Model,), {
            '__module__': __name__, 'Meta': meta,
            'state': fields.Selection(*args, max_length=8, **kwargs)})


class TestTheMergeFollowsTheReference:

    def test_the_documented_example(self):
        model = _model([('a', 'A'), ('b', 'B')])
        extend_selection_choices(model, 'state', [('c', 'C'), ('b',)])
        field = model._meta.get_field('state')
        assert field.selection == [('a', 'A'), ('c', 'C'), ('b', 'B')]
        assert list(field.choices) == [('a', 'A'), ('c', 'C'), ('b', 'B')]

    def test_a_new_label_wins(self):
        model = _model(choices=[('a', 'A'), ('b', 'B')])
        extend_selection_choices(model, 'state', [('a', 'Alfa')])
        assert model._meta.get_field('state').selection == [
            ('a', 'Alfa'), ('b', 'B')]

    def test_extending_twice_does_not_duplicate(self):
        model = _model([('a', 'A')])
        extend_selection_choices(model, 'state', [('b', 'B')])
        extend_selection_choices(model, 'state', [('b', 'B')])
        assert [v for v, _ in model._meta.get_field('state').selection] == [
            'a', 'b']

    def test_the_extended_field_validates_the_new_value(self):
        model = _model([('a', 'A')])
        extend_selection_choices(model, 'state', [('b', 'B')])
        field = model._meta.get_field('state')
        assert field.convert_to_cache('b', None) == 'b'
        with pytest.raises(ValueError):
            field.convert_to_cache('z', None)

    def test_a_new_value_gets_set_null(self):
        model = _model([('a', 'A')])
        added = extend_selection_choices(model, 'state', [('b', 'B')])
        assert added == ['b']
        assert model._meta.get_field('state').ondelete == {'b': 'set null'}

    def test_a_computed_selection_cannot_be_extended(self):
        model = _model('_options')
        with pytest.raises(ValueError, match='selection_add'):
            extend_selection_choices(model, 'state', [('b', 'B')])
