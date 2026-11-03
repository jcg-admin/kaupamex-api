"""Mitad roja: el recordset no resuelve su base por el alias del entorno.

EXPERIMENTAL — medición del ítem ``tag-delete-unlink-other-alias`` del plan:
no es una prueba de la suite, y no se mueve a ``tests/`` mientras el contrato
que mide siga ausente. Su condición de cierre es la de TASK-API-0382.

≙ ``BaseModel`` (``odoo19c: odoo/orm/models.py``): ``create``, ``search``,
``browse`` y ``unlink`` operan sobre ``self.env.cr``, la conexión de **su**
entorno. Aquí la conexión de un entorno es su alias (``Environment._using``),
y las cuatro lo ignoran: eligen base por ``orm.routers``, que decide por
contexto de empresa.

El alias de la prueba apunta a la misma base de pruebas con una conexión y una
transacción propias. Una fila escrita por esa conexión no existe para
``default`` mientras no se confirme, así que las aserciones distinguen en qué
conexión cayó cada operación sin una segunda base física.

Uso, desde la raíz del consumidor, con el entorno de pruebas cargado::

    uv run pytest <banco>/probes/env-alias-recordset -q --reuse-db \\
        -p no:cacheprovider

Medido 2026-11-03 sobre ``d3448691``: ``create`` escribe en ``default`` (la
fila no está en el alias) y ``search_count`` y ``browse`` leen de ``default``.
"""

import io
import textwrap

import pytest
from django.conf import settings
from django.db import connections, transaction

from orm.environments import Environment
from orm.utils import SUPERUSER_ID
from tools.convert import convert_xml_import

PROBE_ALIAS = 'env_alias_recordset_probe'


@pytest.fixture
def probe_alias(django_db_setup, django_db_blocker):
    """Un alias propio sobre la base de pruebas, retirado al terminar.

    Un ``TestCase`` rehúsa todo alias que no declare, así que el acceso va por
    el público ``django_db_blocker``, como en ``test_multidb_isolation``. Las
    dos conexiones quedan dentro de una transacción que se revierte: la prueba
    no deja filas en ninguna.
    """
    assert PROBE_ALIAS not in settings.DATABASES
    default = connections['default'].settings_dict
    settings.DATABASES[PROBE_ALIAS] = dict(default)
    try:
        with django_db_blocker.unblock(), \
                transaction.atomic(using='default'), \
                transaction.atomic(using=PROBE_ALIAS):
            yield PROBE_ALIAS
            transaction.set_rollback(True, using=PROBE_ALIAS)
            transaction.set_rollback(True, using='default')
    finally:
        connections[PROBE_ALIAS].close()
        del connections[PROBE_ALIAS]
        del settings.DATABASES[PROBE_ALIAS]


def _rows(model, alias, pk):
    return model.objects.using(alias).filter(pk=pk).exists()


def test_create_writes_in_the_environment_alias(probe_alias):
    with Environment(probe_alias, SUPERUSER_ID, {}) as env:
        order = env['test_orm.order'].create({})
        model = type(order)
        assert _rows(model, probe_alias, order.id)
        assert not _rows(model, 'default', order.id)


def test_search_and_unlink_act_on_the_environment_alias(probe_alias):
    with Environment(probe_alias, SUPERUSER_ID, {}) as env:
        Order = env['test_orm.order']
        model = Order if isinstance(Order, type) else type(Order)
        row = model.objects.using(probe_alias).create()
        assert Order.search_count([('id', '=', row.pk)]) == 1
        Order.browse(row.pk).unlink()
        assert not _rows(model, probe_alias, row.pk)


def test_a_delete_tag_on_another_alias_goes_through_unlink(probe_alias):
    """≙ ``records.unlink()`` (``odoo19c: odoo/tools/convert.py:265``) con la
    carga en otra base: la sobrescritura de ``test_orm.order.line`` retira la
    línea de recompensa del mismo producto, que el ``QuerySet.delete()`` de
    ``_tag_delete`` sobre la tabla deja viva."""
    with Environment(probe_alias, SUPERUSER_ID, {}) as env:
        Line = env['test_orm.order.line']
        order = env['test_orm.order'].create({})
        Line.create([
            {'order_id': order.id, 'product': 'p', 'reward': False},
            {'order_id': order.id, 'product': 'p', 'reward': True},
        ])
        xml = textwrap.dedent(f'''
            <kaupamex>
              <delete model="test_orm.order.line"
                      search="[('order_id', '=', {order.id}),
                               ('reward', '=', False)]"/>
            </kaupamex>''').strip().encode()
        convert_xml_import('test_orm', io.BytesIO(xml), using=probe_alias)
        assert not Line.search_count([('order_id', '=', order.id)])
