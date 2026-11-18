"""Todo modelo propio recibe los métodos de esquema de la fuente.

≙ ``_auto_init``, ``_check_removed_columns``, ``_add_sql_constraints`` e
``init`` en ``BaseModel`` (``odoo19c: odoo/orm/models.py:3152-3268``), que
``init_models`` llama en todo modelo (``odoo19c: odoo/orm/registry.py:
749-751``). Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/
designs/adopt-schema-hooks.md``.

Desde ``record-loader-universality-0485`` llegan por la MRO: todo modelo
propio hereda ``RecordLoaderMixin``, como todo modelo de la fuente hereda
``BaseModel``, y el adoptador que los colgaba se retiró
(``designs/record-loader-universality.md``).
"""
import pytest
from django.apps import apps
from django.db import connection

from orm.model_classes import THIRD_PARTY_MODULE_PREFIXES
from orm.models import RecordLoaderMixin
from orm.registry import Registry

pytestmark = pytest.mark.django_db

SCHEMA_HOOKS = ('_auto_init', '_check_removed_columns', '_add_sql_constraints',
                'init')


def _own_managed_models():
    return [model for model in apps.get_models()
            if model._meta.managed and not model._meta.proxy
            and not model.__module__.startswith(THIRD_PARTY_MODULE_PREFIXES)]


def test_no_model_carries_a_copy_of_the_mixin_hooks():
    """La huella del adoptador retirado: una función del mixin colgada en el
    diccionario de la propia clase. Un ``init`` declarado por el modelo
    (``res.users``, ``res.company``, ``ir.config_parameter``,
    ``hr.employee.public``, como en la fuente) no lo es."""
    copied = [
        (model._meta.label, name) for model in _own_managed_models()
        for name in SCHEMA_HOOKS
        if name in vars(model)
        and getattr(vars(model)[name], '__func__', None)
        is RecordLoaderMixin.__dict__[name].__func__
    ]
    assert copied == []


def test_every_own_model_resolves_the_schema_hooks():
    missing = [(model._meta.label, name) for model in _own_managed_models()
               for name in SCHEMA_HOOKS
               if getattr(model, name, None) is None]
    assert missing == []


def test_a_declared_init_is_kept():
    public = apps.get_model('hr', 'HrEmployeePublic')
    assert vars(public)['init'].__func__.__qualname__ == (
        'HrEmployeePublic.init')


def test_every_own_managed_model_has_auto_init():
    missing = [model._meta.label for model in _own_managed_models()
               if not hasattr(model, '_auto_init')]
    assert missing == []


def test_init_models_reconciles_a_plain_django_model(db):
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
