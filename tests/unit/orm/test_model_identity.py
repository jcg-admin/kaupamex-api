"""La identidad que guardan las columnas de modelo: el ``_name``.

≙ ``'model': model._name`` en ``_reflect_model_params``
(``odoo19c: odoo/addons/base/models/ir_model.py:428``). Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
model-identity-contract.md``.

*Métrica:* el valor de :func:`orm.registry.identity_of` para un modelo de
cada categoría de la clasificación, y la vuelta por
:func:`orm.registry.identity_for_key` desde las dos formas de nombrarlo.
*Ciega a:* las filas ya guardadas, que reescribe la migración del corte C3.
"""
from django.apps import apps
from django.contrib.auth.models import Group

from addons.base.models import ResPartner
from orm import registry


def test_a_model_with_a_source_name_is_identified_by_it():
    assert registry.identity_of(ResPartner) == 'res.partner'


def test_a_model_without_name_keeps_its_django_label():
    assert registry.identity_of(Group) == 'auth.Group'


def test_an_auto_created_table_keeps_its_django_label():
    through = next(model for model in apps.get_models(
        include_auto_created=True) if model._meta.auto_created)
    assert registry.identity_of(through) == through._meta.label


def test_both_spellings_resolve_to_the_same_identity():
    assert registry.identity_for_key('base.ResPartner') == 'res.partner'
    assert registry.identity_for_key('res.partner') == 'res.partner'


def test_an_unknown_key_is_returned_as_given():
    assert registry.identity_for_key('gone.Model') == 'gone.Model'


def test_every_identity_is_unique_across_the_registry():
    identities = [registry.identity_of(model)
                  for model in apps.get_models(include_auto_created=True)]
    assert len(identities) == len(set(identities))
