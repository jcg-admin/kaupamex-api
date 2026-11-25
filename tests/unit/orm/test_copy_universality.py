"""``copy`` y su cadena en todo modelo concreto propio.

≙ ``copy_data``, ``copy_translations`` y ``copy`` en ``BaseModel``
(``odoo19c: odoo/orm/models.py:5406-5545``): allá **todo** modelo los
tiene. Aquí los lleva ``CopyMixin``, y ``orm.model_classes.adopt_copy``
los entrega a quien no los hereda. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
copy-universality.md``.
"""
import pytest
from django.apps import apps
from django.contrib.auth import get_user_model

from orm.environments import sudo
from orm.model_classes import THIRD_PARTY_MODULE_PREFIXES

pytestmark = pytest.mark.django_db

IrExports = apps.get_model('base', 'IrExports')
ExportJob = apps.get_model('base', 'ExportJob')


def test_a_timestamped_model_duplicates_its_row():
    # ``ir.exports`` es ``BaseModel``: su ACL rige, y la fuente prueba como
    # superusuario.
    with sudo():
        original = IrExports.objects.create(name='Pedidos',
                                            resource='sale.SaleOrder')
        duplicate = original.copy()
        assert duplicate.pk != original.pk
        assert (duplicate.name, duplicate.resource) == ('Pedidos',
                                                        'sale.SaleOrder')
        assert duplicate.create_date >= original.create_date


def test_a_django_only_model_duplicates_its_row():
    """``base.ExportJob`` es propio del L0 y no es ``BaseModel``."""
    user = get_user_model().objects.create_user(
        login='copy.universality@kaupamex.mx', group_ids=[])
    job = ExportJob.objects.create(requested_by=user, file_path='a.csv')
    duplicate = job.copy({'file_path': 'b.csv'})
    assert duplicate.pk != job.pk
    assert duplicate.file_path == 'b.csv'
    assert duplicate.requested_by_id == user.pk


def test_every_own_concrete_model_has_copy():
    missing = [model._meta.label for model in apps.get_models()
               if not model.__module__.startswith(THIRD_PARTY_MODULE_PREFIXES)
               and not model._meta.proxy
               and not callable(getattr(model, 'copy', None))]
    assert missing == []
