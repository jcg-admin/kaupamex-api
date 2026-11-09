"""Índice parcial de un campo dependiente de empresa.

≙ ``Registry.check_indexes`` (``odoo19c: odoo/orm/registry.py:871-882``):
con ``index='btree_not_null'`` y ``company_dependent`` la referencia crea un
btree sobre ``("col" IS NOT NULL)`` con ``WHERE "col" IS NOT NULL``. Diseño en
``designs/company-dependent-partial-index.md`` del Workbench.

*Métrica:* definición de los índices de la tabla en ``pg_indexes``.
*Ciega a:* el nombre del índice (divergencia declarada por ``models.E034``).
"""
import pytest
from django.apps import apps
from django.db import connection

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize('label, field_name', [
    ('base.ResPartner', 'barcode'),
    ('analytic.AccountAnalyticPlan', 'default_applicability'),
])
def test_the_table_carries_the_partial_expression_index(label, field_name):
    model = apps.get_model(label)
    column = model._meta.get_field(field_name).column
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT indexdef FROM pg_indexes WHERE tablename = %s",
            [model._meta.db_table])
        definitions = [row[0] for row in cursor.fetchall()]
    expected = f'({column} IS NOT NULL)'
    assert any(definition.count(expected) == 2
               for definition in definitions), definitions
