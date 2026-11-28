"""Versiones de ``ir.module.module``.

≙ ``odoo19c: odoo/addons/base/models/ir_module.py:211-215,285-291``: la
columna ``latest_version`` guarda lo instalado, ``installed_version`` se
calcula desde el manifiesto y ``published_version`` se persiste. Diseño:
``designs/ir-module-versions.md``.
"""

import pytest
from django.db import connection

from addons.base.models import IrModule
from orm.environments import Environment
from orm.utils import SUPERUSER_ID

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def _columns():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'ir_module_module'")
        return {row[0] for row in cursor.fetchall()}


def test_the_installed_version_lives_in_latest_version():
    columns = _columns()
    assert 'latest_version' in columns
    assert 'installed_version' not in columns


def test_published_version_is_stored():
    assert 'published_version' in _columns()


def test_installed_version_is_computed_from_the_manifest():
    module = IrModule.objects.get(name='base')
    record = Environment(uid=SUPERUSER_ID)['ir.module.module'].browse(
        module.id)
    expected = record.get_module_info('base').get('version')
    assert record.installed_version == expected
    field = IrModule._meta.get_field('installed_version')
    assert field.compute == '_get_latest_version' and not field.store
