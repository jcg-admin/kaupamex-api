"""``country_ids`` de ``ir.module.module``.

≙ ``odoo19c: odoo/addons/base/models/ir_module.py:297``: un ``Many2many`` a
``res.country`` por la tabla ``module_country`` con las columnas
``module_id`` y ``country_id``. Diseño: ``designs/ir-module-country-ids.md``.
"""

import pytest
from django.db import connection

from addons.base.models import IrModule, ResCountry
from orm.environments import Environment
from orm.utils import SUPERUSER_ID

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def test_the_relation_table_keeps_the_source_names():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'module_country'")
        columns = {row[0] for row in cursor.fetchall()}
    assert {'module_id', 'country_id'} <= columns


def test_countries_are_read_from_the_module():
    module = IrModule.objects.create(name='cty_owner', shortdesc='Owner')
    country = ResCountry.objects.order_by('id').first()
    with connection.cursor() as cursor:
        cursor.execute(
            'INSERT INTO module_country (module_id, country_id) '
            'VALUES (%s, %s)', [module.id, country.id])
    record = Environment(uid=SUPERUSER_ID)['ir.module.module'].browse(
        module.id)
    assert record.country_ids.ids == [country.id]
