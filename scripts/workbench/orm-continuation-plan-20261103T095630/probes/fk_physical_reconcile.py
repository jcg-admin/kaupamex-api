"""EXPERIMENTAL: cada FK física de pg_constraint con su campo y su dueño.

Medición exploratoria escrita antes de cerrar Search Existing: no es
autoridad, ni producto, ni evidencia de aceptación por sí sola. Solo lee.

Uso: python fk_physical_reconcile.py <salida.tsv>
"""
import collections
import csv
import importlib
import sys

import django

THIRD = ('django.', 'rest_framework')


def field_index(apps, models):
    """``{(tabla, columna): (clase, dueño, campo)}`` de todo campo con FK."""
    index = {}
    for model in apps.get_models(include_auto_created=True):
        meta = model._meta
        third = model.__module__.startswith(THIRD)
        for field in meta.local_fields:
            if isinstance(field, models.ForeignKey) and field.db_constraint:
                if meta.auto_created:
                    kind = 'many2many (tabla automática)'
                elif third:
                    kind = 'modelo de Django o de terceros'
                else:
                    kind = 'many2one de modelo propio'
                index[(meta.db_table, field.column)] = (
                    kind, meta.label, field.name)
    return index


def main(out):
    django.setup()
    apps = importlib.import_module('django.apps').apps
    db = importlib.import_module('django.db')
    models = importlib.import_module('django.db.models')
    index = field_index(apps, models)
    with db.connection.cursor() as cr:
        cr.execute("""
            SELECT fk.conname, c1.relname, a1.attname, c2.relname,
                   fk.confdeltype, fk.condeferrable
              FROM pg_constraint fk
              JOIN pg_class c1 ON fk.conrelid = c1.oid
              JOIN pg_class c2 ON fk.confrelid = c2.oid
              JOIN pg_attribute a1 ON a1.attrelid = c1.oid
                                  AND fk.conkey[1] = a1.attnum
             WHERE fk.contype = 'f'
               AND c1.relnamespace = current_schema::regnamespace""")
        constraints = cr.fetchall()
    summary = collections.Counter()
    with open(out, 'w', newline='', encoding='utf-8') as handle:
        writer = csv.writer(handle, delimiter='\t', lineterminator='\n')
        writer.writerow(['constraint', 'table', 'column', 'target',
                         'confdeltype', 'deferrable', 'kind', 'model',
                         'field'])
        for name, table, column, target, deltype, deferrable in constraints:
            kind, label, field = index.get(
                (table, column), ('restricción sin campo', '-', '-'))
            summary[kind] += 1
            writer.writerow([name, table, column, target, deltype,
                             deferrable, kind, label, field])
    print('FK físicas:', len(constraints))
    for kind, count in summary.most_common():
        print(f'  {kind}: {count}')


if __name__ == '__main__':
    main(sys.argv[1])
