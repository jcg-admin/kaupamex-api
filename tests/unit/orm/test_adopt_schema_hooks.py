"""Todo modelo propio recibe los métodos de esquema de la fuente.

≙ ``_auto_init``, ``_check_removed_columns``, ``_add_sql_constraints`` e
``init`` en ``BaseModel`` (``odoo19c: odoo/orm/models.py:3152-3268``), que
``init_models`` llama en todo modelo (``odoo19c: odoo/orm/registry.py:
749-751``). Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/
designs/adopt-schema-hooks.md``.
"""
import pytest
from django.apps import apps
from django.db import connection

from orm.model_classes import SCHEMA_HOOKS, THIRD_PARTY_MODULE_PREFIXES
from orm.models import RecordLoaderMixin
from orm.registry import Registry

pytestmark = pytest.mark.django_db


def _own_managed_models():
    return [model for model in apps.get_models()
            if model._meta.managed and not model._meta.proxy
            and not model.__module__.startswith(THIRD_PARTY_MODULE_PREFIXES)]


def test_a_model_outside_the_loader_resolves_the_schema_hooks():
    country = apps.get_model('base', 'ResCountry')
    assert not issubclass(country, RecordLoaderMixin)
    for name in SCHEMA_HOOKS:
        assert (getattr(country, name).__func__
                is RecordLoaderMixin.__dict__[name].__func__), name


def test_a_declared_init_is_kept():
    public = apps.get_model('hr', 'HrEmployeePublic')
    assert vars(public)['init'].__func__.__qualname__ == (
        'HrEmployeePublic.init')


def test_every_own_managed_model_has_auto_init():
    missing = [model._meta.label for model in _own_managed_models()
               if not hasattr(model, '_auto_init')]
    assert missing == []


def test_init_models_reconciles_a_model_outside_the_loader(db):
    with connection.cursor() as cr:
        cr.execute('ALTER TABLE res_country ADD COLUMN orphan_flag integer '
                   'NOT NULL DEFAULT 0')
    registry = Registry(connection.alias)
    with connection.cursor() as cr:
        registry.init_models(cr, ['res.country'], {'module': 'base'},
                             install=False)
        cr.execute("SELECT is_nullable FROM information_schema.columns "
                   "WHERE table_name = 'res_country' "
                   "AND column_name = 'orphan_flag'")
        assert cr.fetchone()[0] == 'YES'
