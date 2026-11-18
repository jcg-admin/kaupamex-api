"""Un Many2one leído sobre el conjunto vacío es el valor nulo del campo.

≙ ``Field.__get__`` (``odoo19c: odoo/orm/fields.py:1659``): «null record ->
return the null value for this field». Para un comodelo ``BaseModel`` es su
recordset vacío; para uno de Django, que no tiene recordset, ``None``.

*Métrica:* el valor devuelto y el número de consultas.
*Ciega a:* los campos que no son Many2one, cuya lectura sobre el vacío va
por ``FieldDescriptor``.
"""
import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from orm.environments import env as current_env
from orm.environments import sudo

pytestmark = pytest.mark.django_db


@pytest.fixture
def environment():
    with sudo():
        yield current_env()


def test_a_django_comodel_reads_as_none(environment):
    empty = environment['test_orm.multi'].browse()
    with CaptureQueriesContext(connection) as queries:
        assert empty.partner is None
    assert len(queries) == 0


def test_a_basemodel_comodel_reads_as_its_empty_recordset(environment):
    empty = environment['test_orm.multi.line'].browse()
    with CaptureQueriesContext(connection) as queries:
        value = empty.multi
    assert value._name == 'test_orm.multi'
    assert not value
    assert len(queries) == 0
