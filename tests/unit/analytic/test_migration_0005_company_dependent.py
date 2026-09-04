"""Control de ida y vuelta de la migración 0005 de ``analytic``.

``default_applicability`` pasó de ``varchar(16)`` escalar a ``jsonb`` por
empresa. El ``AlterField`` que ``makemigrations`` genera **falla sobre
datos** (``'optional'::jsonb`` es un error de sintaxis JSON), así que la
migración lleva SQL escrito a mano. Este archivo mide ese SQL contra datos
reales, en los dos sentidos.

Por qué el control existe, y qué lo haría fallar
================================================

Que la migración esté aplicada no dice nada sobre si conserva el dato: se
aplicó sobre una tabla vacía. Un control que sólo comprobara
``data_type == 'jsonb'`` pasaría igual con un ``USING '{}'::jsonb`` que
tirara todos los valores — el verde no distinguiría *"reparte el escalar"*
de *"lo borra"* (sub-patrón D de ``metrica-decide-la-conclusion``).

Por eso cada caso **siembra un valor y lo persigue**: si el reparto por
empresa desaparece, si la vuelta atrás no recupera el escalar, o si el
``ALTER`` revienta sobre una fila con dato, el caso cae.

El SQL se lee del propio módulo de migración —no se copia aquí— para que un
cambio en la migración se mida contra este control y no contra su copia.

El control se probó contra su propio fallo
==========================================

Se sustituyó el bloque de ida por el ``AlterField`` que ``makemigrations``
genera —``TYPE jsonb USING default_applicability::jsonb``— sobre una fila
con ``'optional'``, y la sonda cayó con
``DataError: invalid input syntax for type json``. Ese es el fallo que este
archivo distingue: sin él, un verde aquí no diría si el SQL a mano hacía
falta.
"""
import importlib
import json

import pytest
from django.db import connection

from addons.base.models import ResCompany

MIGRATION = importlib.import_module(
    'addons.analytic.migrations'
    '.0005_alter_accountanalyticplan_default_applicability')


def _column_type():
    with connection.cursor() as cursor:
        cursor.execute(
            "select data_type from information_schema.columns "
            "where table_name = 'account_analytic_plan' "
            "and column_name = 'default_applicability'")
        return cursor.fetchone()[0]


def _run(sql):
    """Corre un bloque de la migración dentro de la transacción del test.

    ``SET CONSTRAINTS ALL IMMEDIATE`` es obligatorio antes del ``ALTER``:
    pytest-django deja las FK diferidas, y PostgreSQL rehúsa alterar una
    tabla con eventos de trigger pendientes de la siembra
    (``cannot ALTER TABLE ... because it has pending trigger events``).
    Fuera del test la migración corre en su propia transacción, sin
    inserciones previas, así que ahí el problema no existe.
    """
    with connection.cursor() as cursor:
        cursor.execute('SET CONSTRAINTS ALL IMMEDIATE')
        cursor.execute(sql)


def _seed_plan(cursor, applicability):
    """Inserta un plan por SQL — el modelo ya declara el campo como ``jsonb``."""
    cursor.execute(
        "insert into account_analytic_plan "
        "  (name, description, parent_path, default_applicability, "
        "   sequence, color) "
        "values (%s, '', '', %s, 10, 0) returning id",
        ['Plan de control', applicability])
    return cursor.fetchone()[0]


def _read_plan(cursor, plan_id):
    """El valor crudo — el cursor no decodifica el ``jsonb`` como el campo."""
    cursor.execute(
        "select default_applicability from account_analytic_plan where id = %s",
        [plan_id])
    return cursor.fetchone()[0]


def _read_map(cursor, plan_id):
    return json.loads(_read_plan(cursor, plan_id))


@pytest.mark.django_db(transaction=False)
class TestRoundTrip:
    """PostgreSQL tiene DDL transaccional: la transacción del test lo revierte."""

    def test_the_column_starts_out_as_jsonb(self):
        assert _column_type() == 'jsonb'

    def test_going_back_recovers_the_scalar_of_the_lowest_company(self):
        company = ResCompany.objects.create(code='ctl-0005', name='Control')
        with connection.cursor() as cursor:
            plan_id = _seed_plan(cursor, '{"%d": "unavailable"}' % company.id)

        _run(MIGRATION.A_VARCHAR)

        assert _column_type() == 'character varying'
        with connection.cursor() as cursor:
            assert _read_plan(cursor, plan_id) == 'unavailable'

    def test_going_back_falls_back_to_optional_when_the_map_is_empty(self):
        with connection.cursor() as cursor:
            plan_id = _seed_plan(cursor, '{}')

        _run(MIGRATION.A_VARCHAR)

        with connection.cursor() as cursor:
            assert _read_plan(cursor, plan_id) == 'optional'

    def test_going_forward_spreads_the_scalar_over_every_company(self):
        una = ResCompany.objects.create(code='ctl-0005-a', name='Una')
        otra = ResCompany.objects.create(code='ctl-0005-b', name='Otra')
        with connection.cursor() as cursor:
            plan_id = _seed_plan(cursor, '{"%d": "mandatory"}' % una.id)

        _run(MIGRATION.A_VARCHAR)          # deja el escalar 'mandatory'
        _run(MIGRATION.A_JSONB)            # y lo reparte entre las dos

        assert _column_type() == 'jsonb'
        with connection.cursor() as cursor:
            mapa = _read_map(cursor, plan_id)
        assert mapa == {str(una.id): 'mandatory', str(otra.id): 'mandatory'}

    def test_the_forward_survives_a_row_holding_its_old_default(self):
        """El caso exacto que el ``AlterField`` generado no soportaba.

        Con ``USING default_applicability::jsonb`` el ``ALTER`` revienta aquí:
        ``'optional'`` no es JSON válido. Que este caso pase es la única
        evidencia de que la migración escrita a mano hacía falta.
        """
        company = ResCompany.objects.create(code='ctl-0005-c', name='Con dato')
        with connection.cursor() as cursor:
            plan_id = _seed_plan(cursor, '{}')

        _run(MIGRATION.A_VARCHAR)
        with connection.cursor() as cursor:
            assert _read_plan(cursor, plan_id) == 'optional'

        _run(MIGRATION.A_JSONB)

        with connection.cursor() as cursor:
            assert _read_map(cursor, plan_id) == {str(company.id): 'optional'}

    def test_the_forward_leaves_an_empty_map_as_the_column_default(self):
        _run(MIGRATION.A_VARCHAR)
        _run(MIGRATION.A_JSONB)
        with connection.cursor() as cursor:
            cursor.execute(
                "select column_default from information_schema.columns "
                "where table_name = 'account_analytic_plan' "
                "and column_name = 'default_applicability'")
            assert cursor.fetchone()[0] == "'{}'::jsonb"
