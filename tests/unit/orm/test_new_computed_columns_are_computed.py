"""Toda columna calculada que una migración añade se calcula en una migración.

≙ ``odoo19c: odoo/orm/models.py:3220-3238``. Guardián de TASK-API-0516:
cada ``AddField`` de un calculado almacenado, fuera de una migración inicial,
tiene en su app una operación ``ComputeStoredFields`` que lo nombra. Diseño
en ``designs/compute-new-stored-columns.md`` del Workbench.

*Métrica:* las operaciones de las migraciones en disco.
*Ciega a:* el orden relativo de la columna y de su cómputo dentro de la app
(lo fijan las dependencias de la migración de rescate), y a un campo que se
vuelve calculado por ``AlterField``.
"""
import pytest
from django.apps import apps
from django.core.exceptions import FieldDoesNotExist
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.operations import AddField

from orm.migration_operations import ComputeStoredFields

pytestmark = pytest.mark.django_db


def _added_computed_columns(loader):
    for (app, name), migration in loader.disk_migrations.items():
        if getattr(migration, 'initial', False):
            continue
        for operation in migration.operations:
            if not isinstance(operation, AddField):
                continue
            try:
                field = apps.get_model(app, operation.model_name)._meta \
                    .get_field(operation.name)
            except (LookupError, FieldDoesNotExist):
                continue
            if getattr(field, 'compute', None) and getattr(
                    field, 'store', False):
                yield app, operation.model_name, operation.name


def _computed(loader):
    return {(operation.app_label, operation.model_name, name)
            for migration in loader.disk_migrations.values()
            for operation in migration.operations
            if isinstance(operation, ComputeStoredFields)
            for name in operation.field_names}


def test_every_added_computed_column_is_computed():
    loader = MigrationLoader(connection, ignore_no_migrations=True)
    computed = _computed(loader)
    missing = sorted({key for key in _added_computed_columns(loader)
                      if key not in computed})
    assert missing == []
