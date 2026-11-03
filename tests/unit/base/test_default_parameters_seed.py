"""``_DEFAULT_PARAMETERS`` y su siembra.

≙ ``_default_parameters`` (``odoo19c: odoo/addons/base/models/
ir_config_parameter.py:18-25``) e ``init`` (``:43-56``), que la fuente llama
desde el ``post_init`` de ``base``. Aquí lo llama la migración de datos de
``base``: sin ella una base creada sólo con ``migrate`` no tenía
``database.secret`` y ``tools.misc.hmac`` no podía firmar.
"""

import importlib

import pytest
from django.apps import apps as django_apps

from addons.base.models.ir_config_parameter import _DEFAULT_PARAMETERS, SystemParameter

SOURCE_KEYS = {
    'database.secret', 'database.uuid', 'database.create_date',
    'web.base.url', 'base.login_cooldown_after', 'base.login_cooldown_duration',
}

seed_migration = importlib.import_module(
    'addons.base.migrations.0094_seed_default_parameters')


def test_the_spec_carries_every_key_of_the_source():
    assert SOURCE_KEYS <= set(_DEFAULT_PARAMETERS)


def test_the_source_values_are_kept():
    assert _DEFAULT_PARAMETERS['base.login_cooldown_after']() == 10
    assert _DEFAULT_PARAMETERS['base.login_cooldown_duration']() == 60
    assert _DEFAULT_PARAMETERS['web.base.url']().startswith('http://localhost:')


class _Editor:
    class connection:
        alias = 'default'


@pytest.mark.django_db
def test_the_migration_seeds_missing_keys_and_keeps_existing_ones():
    SystemParameter.objects.filter(key__in=_DEFAULT_PARAMETERS).delete()
    SystemParameter.objects.create(key='database.secret', value='kept')
    seed_migration.seed(django_apps, _Editor())
    stored = dict(SystemParameter.objects.filter(
        key__in=_DEFAULT_PARAMETERS).values_list('key', 'value'))
    assert set(stored) == set(_DEFAULT_PARAMETERS)
    assert stored['database.secret'] == 'kept'
