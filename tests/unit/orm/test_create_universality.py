"""``create`` y ``default_get`` en todo modelo concreto propio.

≙ ``create``, ``_create`` y ``default_get`` en ``BaseModel``
(``odoo19c: odoo/orm/models.py:4611-4930``): allá **todo** modelo los tiene.
Aquí los lleva ``DefaultGetMixin``, y ``orm.model_classes.adopt_create``
los entrega a quien no los hereda. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
create-universality.md``.
"""
import pytest
from django.apps import apps

from orm.commands import _row_id
from orm.environments import sudo
from orm.model_classes import THIRD_PARTY_MODULE_PREFIXES

pytestmark = pytest.mark.django_db

IrExports = apps.get_model('base', 'IrExports')


def test_create_takes_a_list_and_keeps_its_order():
    with sudo():
        rows = IrExports.create([{'name': 'Uno', 'resource': 'a.B'},
                                 {'name': 'Dos', 'resource': 'a.B'}])
    assert [row.name for row in rows] == ['Uno', 'Dos']
    # los dos campos declaran ``default=''``
    assert IrExports.default_get(['name', 'resource']) == {
        'name': '', 'resource': ''}


def test_name_create_goes_through_create(monkeypatch):
    seen = []
    original = IrExports.create.__func__

    def spy(cls, vals_list):
        seen.append(vals_list)
        return original(cls, vals_list)

    monkeypatch.setattr(IrExports, '_rec_name', 'name', raising=False)
    monkeypatch.setattr(IrExports, 'create', classmethod(spy))
    with sudo():
        created = IrExports.name_create('Por nombre')
    assert seen and seen[0] in ({'name': 'Por nombre'},
                                [{'name': 'Por nombre'}])
    assert IrExports.objects.get(pk=created[0]).name == 'Por nombre'


def test_every_own_concrete_model_has_create():
    missing = [model._meta.label for model in apps.get_models()
               if not model.__module__.startswith(THIRD_PARTY_MODULE_PREFIXES)
               and not model._meta.proxy
               and not callable(getattr(model, 'create', None))]
    assert missing == []


def test_a_command_takes_the_id_of_a_created_queryset():
    """``Command.create`` sobre un comodelo sin ``BaseModel`` enlaza la fila:
    ``_row_id`` lee el pk del ``QuerySet`` que devuelve ``create``."""
    with sudo():
        rows = IrExports.create([{'name': 'Fila', 'resource': 'a.B'}])
    assert _row_id(rows) == rows.get().pk
