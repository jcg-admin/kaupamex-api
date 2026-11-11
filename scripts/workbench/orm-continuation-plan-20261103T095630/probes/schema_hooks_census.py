"""EXPERIMENTAL: qué harían los métodos de esquema en los modelos sin ellos.

Medición exploratoria escrita antes de cerrar Search Existing: no es
autoridad, ni producto, ni evidencia de aceptación por sí sola. Solo lee.
"""
import collections
import importlib

import django

THIRD = ('django.', 'rest_framework')


def main():
    django.setup()
    apps = importlib.import_module('django.apps').apps
    db = importlib.import_module('django.db')
    sql = importlib.import_module('tools.sql')
    orm_models = importlib.import_module('orm.models')
    recorder = importlib.import_module('django.db.migrations.recorder')
    applied = {app for app, _ in recorder.MigrationRecorder(
        db.connection).applied_migrations()}
    rows = []
    for model in apps.get_models():
        meta = model._meta
        if model.__module__.startswith(THIRD) or hasattr(model, '_auto_init'):
            continue
        kind = ('proxy' if meta.proxy else 'abstract' if meta.abstract
                else 'managed' if meta.managed else 'unmanaged')
        declared = {field.column for field in meta.concrete_fields}
        orphans = []
        if kind == 'managed':
            with db.connection.cursor() as cr:
                if sql.table_exists(cr, meta.db_table):
                    cr.execute(
                        'SELECT a.attname FROM pg_attribute a '
                        'JOIN pg_class c ON a.attrelid = c.oid '
                        'WHERE c.relname = %s AND a.attnum > 0 '
                        'AND NOT a.attisdropped AND a.attnotnull',
                        [meta.db_table])
                    orphans = [name for (name,) in cr.fetchall()
                               if name not in declared]
        rows.append({
            'label': meta.label,
            'kind': kind,
            'migration_owner': meta.app_label if meta.app_label in applied
            else '-',
            'table_objects': len(getattr(model, '_table_objects', None)
                                 or {}),
            'own_init': 'init' in vars(model),
            'orphan_not_null': orphans,
            'base_model': issubclass(model, orm_models.BaseModel),
        })
    print('modelos sin _auto_init (propios):', len(rows))
    print('por tipo:', dict(collections.Counter(r['kind'] for r in rows)))
    print('con migración aplicada de su app:',
          sum(r['migration_owner'] != '-' for r in rows))
    print('con objetos de tabla:',
          [(r['label'], r['table_objects']) for r in rows
           if r['table_objects']])
    print('con init propio:', [r['label'] for r in rows if r['own_init']])
    print('con columnas huérfanas NOT NULL:',
          [(r['label'], r['orphan_not_null']) for r in rows
           if r['orphan_not_null']])
    print('derivan de BaseModel:', sum(r['base_model'] for r in rows))
    print('por app:', dict(collections.Counter(
        r['label'].split('.')[0] for r in rows).most_common()))


if __name__ == '__main__':
    main()
