"""El recordset usa la base de su entorno, también fuera de ``default``.

≙ ``BaseModel`` (``odoo19c: odoo/orm/models.py``): ``create``, ``search``,
``browse`` y ``unlink`` operan sobre ``self.env.cr``, la conexión de **su**
entorno. Aquí la conexión de un entorno es su alias (``Environment._using``),
y ``Environment.__enter__`` la publica en el canal ``_cr``, que
``orm.routers`` consulta antes de enrutar por empresa.

El alias de la prueba apunta a la misma base de pruebas con una conexión y una
transacción propias. Una fila escrita por esa conexión no existe para
``default`` mientras no se confirme, así que las aserciones distinguen en qué
conexión cayó cada operación sin una segunda base física.

Nació como la mitad roja del ítem ``tag-delete-unlink-other-alias``
(``scripts/workbench/orm-continuation-plan-20261103T095630``), medida en
``d3448691``: ``create`` escribía en ``default`` y ``search_count`` y
``browse`` leían de ``default``. Retirar el canal, o su lectura en el
enrutador, tumba los tres casos.
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
