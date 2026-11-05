"""Equivalencia en PostgreSQL de las formas SQL que ``tools.query`` traduce.

La referencia (``odoo19c: odoo/tools/query.py``) escribe ``col IN %s`` con una
tupla, que psycopg 2 expande a ``col IN (v1, ..., vn)``. El puerto escribe
``col = ANY(%s)`` y ``col IN (SELECT unnest(%s))`` con una lista, porque
psycopg 3 no expande una tupla. Esta medición evalúa, fila por fila y con el
valor de verdad de tres estados (``true``, ``false``, ``null``), la forma de la
referencia —compuesta con un marcador por elemento, que es lo que psycopg 2
emite— contra la del puerto, sobre el PostgreSQL y el psycopg instalados.

La conexión toma los parámetros de ``config.settings.testing`` (la base de
pruebas, por socket) sin imprimirlos. La salida es ``outputs/result.json``; el
código de salida es 0 si todas las comparaciones coinciden y 1 si alguna
difiere.
"""
import json
import pathlib
import sys

import django
import psycopg
from django.db import connections

HERE = pathlib.Path(__file__).resolve().parent
COLUMNS = {
    'int': ('int4', [1, 2, 3, None]),
    'text': ('text', ['a', 'b', 'c', None]),
}
LISTS = {
    'int': [[1], [1, 2], [2, 2, 5], [1, None], [None], [4]],
    'text': [['a'], ['a', 'c'], ['b', 'b'], ['a', None], [None]],
}
# Pares (referencia, puerto): {col} es la columna; {ref} la lista expandida.
FORMS = {
    'in vs any': ('{col} IN ({ref})', '{col} = ANY(%s)'),
    'not in vs not any': ('{col} NOT IN ({ref})', 'NOT ({col} = ANY(%s))'),
    'in vs in unnest': ('{col} IN ({ref})', '{col} IN (SELECT unnest(%s))'),
    'not in vs not in unnest': ('{col} NOT IN ({ref})',
                                '{col} NOT IN (SELECT unnest(%s))'),
}


def truth_table(conn, cursor, sql_type, values, predicate, params):
    """Filas ``[v, predicado]``, o la clase y el mensaje del error SQL."""
    rows = ', '.join(f'(%s::{sql_type})' for _ in values)
    try:
        with conn.transaction():
            cursor.execute(
                f'SELECT v, ({predicate}) FROM (VALUES {rows}) AS t(v) '
                'ORDER BY v NULLS LAST', [*params, *values])
            return [list(row) for row in cursor.fetchall()]
    except psycopg.Error as error:
        return {'error': type(error).__name__,
                'message': str(error).splitlines()[0]}


def main():
    django.setup()
    params = connections['default'].get_connection_params()
    params.pop('cursor_factory', None)
    params.pop('context', None)
    results = []
    with psycopg.connect(**params) as conn:
        with conn.cursor() as cursor:
            cursor.execute('SHOW server_version')
            server = cursor.fetchone()[0]
            for kind, (sql_type, values) in COLUMNS.items():
                for items in LISTS[kind]:
                    for name, (reference, ported) in FORMS.items():
                        expanded = ', '.join('%s' for _ in items)
                        ref_sql = reference.format(col='v', ref=expanded)
                        port_sql = ported.format(col='v')
                        expected = truth_table(conn, cursor, sql_type,
                                               values, ref_sql, items)
                        actual = truth_table(conn, cursor, sql_type,
                                             values, port_sql, [list(items)])
                        results.append({
                            'type': sql_type, 'items': items, 'form': name,
                            'reference': expected, 'ported': actual,
                            'equal': expected == actual})
            conn.rollback()
    report = {
        'postgresql': server, 'psycopg': psycopg.__version__,
        'python': sys.version.split()[0], 'comparisons': len(results),
        'divergent': [r for r in results if not r['equal']],
        'results': results,
    }
    (HERE / 'outputs' / 'result.json').write_text(
        json.dumps(report, indent=1, ensure_ascii=False) + '\n')
    print(f"{report['comparisons']} comparaciones, "
          f"{len(report['divergent'])} divergentes; PostgreSQL {server}, "
          f"psycopg {psycopg.__version__}")
    return 1 if report['divergent'] else 0


if __name__ == '__main__':
    sys.exit(main())
