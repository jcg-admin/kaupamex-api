"""Calcula sobre las filas existentes los calculados almacenados que una
migración anterior de esta app añadió sin calcular.

≙ ``odoo19c: odoo/orm/models.py:3220-3238``. Las dependencias son las hojas
vigentes de las apps cuyos campos lee el cómputo, medidas con
``registry.field_depends`` (TASK-API-0516).
"""
from django.db import migrations

from orm.migration_operations import ComputeStoredFields


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0102_company_dependent_not_null_index'),
    ]

    operations = [
        ComputeStoredFields('base', 'respartner', [
            'commercial_company_name',
            'commercial_partner_id',
        ]),
    ]
