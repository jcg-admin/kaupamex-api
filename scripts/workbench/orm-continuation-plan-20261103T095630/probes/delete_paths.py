"""EXPERIMENTAL: borrado del Collector frente al ON DELETE de PostgreSQL.

Medición exploratoria escrita antes de cerrar Search Existing: no es
autoridad, ni producto, ni evidencia de aceptación por sí sola. Todo ocurre
dentro de una transacción que se revierte.
"""
import importlib

import django

INSERT_CATEGORY = (
    'INSERT INTO test_orm_category '
    '(name, parent, created_at, updated_at, parent_path) '
    'VALUES (%s, %s, now(), now(), %s) RETURNING id')


class Rollback(Exception):
    """Fuerza la reversión de la transacción de la medición."""


def show(label, value):
    print(f'{label}: {value}')


def orm_unlink(env, seen, connection):
    category = env['test_orm.category']
    parent = category.create({'name': 'probe-parent'})
    child = category.create({'name': 'probe-child', 'parent': parent.id})
    seen.clear()
    parent.unlink()
    with connection.cursor() as cr:
        cr.execute('SELECT count(*) FROM test_orm_category WHERE id = %s',
                   [child.id])
        show('1 ORM unlink (Collector, on_delete=CASCADE) hijo restante',
             cr.fetchone()[0])
    show('1 señales pre_delete', seen)


def sql_cascade(cr):
    cr.execute('CREATE TEMP TABLE probe_p (id serial primary key)')
    cr.execute('CREATE TEMP TABLE probe_c (id serial primary key, p int '
               'REFERENCES probe_p(id) ON DELETE CASCADE)')
    cr.execute('INSERT INTO probe_p DEFAULT VALUES RETURNING id')
    parent = cr.fetchone()[0]
    cr.execute('INSERT INTO probe_c (p) VALUES (%s)', [parent])
    cr.execute('DELETE FROM probe_p WHERE id = %s', [parent])
    cr.execute('SELECT count(*) FROM probe_c')
    show('2 SQL DELETE con ON DELETE CASCADE, hijos restantes',
         cr.fetchone()[0])


def deferred_django_fk(cr):
    cr.execute(INSERT_CATEGORY, ['p2', None, '0/'])
    parent = cr.fetchone()[0]
    cr.execute(INSERT_CATEGORY, ['c2', parent, '0/1/'])
    cr.execute('SAVEPOINT s1')
    cr.execute('DELETE FROM test_orm_category WHERE id = %s', [parent])
    show('3 SQL DELETE contra FK diferida de Django: aceptado al momento',
         'sí')
    try:
        cr.execute('SET CONSTRAINTS ALL IMMEDIATE')
        show('3 al forzar la comprobación', 'sin error')
    except Exception as error:
        show('3 al forzar la comprobación',
             type(error).__name__ + ': ' + str(error).splitlines()[0])
        cr.execute('ROLLBACK TO SAVEPOINT s1')
    cr.execute('SET CONSTRAINTS ALL DEFERRED')


def sql_restrict(cr):
    cr.execute('CREATE TEMP TABLE probe_r (id serial primary key, p int '
               'REFERENCES probe_p(id) ON DELETE RESTRICT)')
    cr.execute('INSERT INTO probe_p DEFAULT VALUES RETURNING id')
    parent = cr.fetchone()[0]
    cr.execute('INSERT INTO probe_r (p) VALUES (%s)', [parent])
    cr.execute('SAVEPOINT s2')
    try:
        cr.execute('DELETE FROM probe_p WHERE id = %s', [parent])
        show('4 RESTRICT', 'aceptado')
    except Exception as error:
        show('4 RESTRICT (no diferible) error inmediato',
             type(error).__name__)
        cr.execute('ROLLBACK TO SAVEPOINT s2')


def main():
    django.setup()
    db = importlib.import_module('django.db')
    signals = importlib.import_module('django.db.models.signals')
    environments = importlib.import_module('orm.environments')
    utils = importlib.import_module('orm.utils')
    seen = []
    signals.pre_delete.connect(
        lambda sender, **kwargs: seen.append(sender._meta.db_table),
        weak=False)
    try:
        with db.transaction.atomic():
            with environments.Environment(None, utils.SUPERUSER_ID, {}) as env:
                orm_unlink(env, seen, db.connection)
            with db.connection.cursor() as cr:
                sql_cascade(cr)
                deferred_django_fk(cr)
                sql_restrict(cr)
            raise Rollback
    except Rollback:
        print('revertido')


if __name__ == '__main__':
    main()
