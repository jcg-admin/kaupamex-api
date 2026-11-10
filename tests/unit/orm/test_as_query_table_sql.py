"""``BaseModel._as_query`` nombra la tabla con ``_table_sql``.

``odoo19c: odoo/orm/models.py:5402`` arma ``Query(self.env, self._table,
self._table_sql)``: para un modelo con ``_table_query`` la consulta lee de
esa subconsulta, no de una tabla con el nombre del modelo. El puerto pasaba
sólo ``self._table``, y ``Query`` tomaba entonces el identificador.

Se mide sobre ``ir.attachment`` sustituyendo su ``_table_query`` durante la
prueba: sin ella, la tabla de la consulta es el identificador; con ella, la
subconsulta entre paréntesis.

*Métrica:* el ``SQL`` que la ``Query`` guarda para el alias del modelo.
*Ciega a:* ``_search``, ``exists`` y los bloqueos, que aquí siguen otro
mecanismo declarado en sus docstrings.
"""
import pytest
from django.apps import apps

from orm.environments import env as current_env

pytestmark = pytest.mark.django_db


def _model():
    return next(model for model in apps.get_models()
                if getattr(model, '_name', None) == 'ir.attachment')


def _table(query, model):
    return query._tables[model._table]


def test_a_plain_table_keeps_its_identifier():
    model = _model()
    records = current_env()[model._name].browse((1,))
    assert _table(records._as_query(), model).code == '"ir_attachment"'


def test_a_table_query_is_what_the_query_reads(monkeypatch):
    model = _model()
    monkeypatch.setattr(model, '_table_query', 'SELECT 1 AS id')
    records = current_env()[model._name].browse((1,))
    assert _table(records._as_query(), model).code == '(SELECT 1 AS id)'
