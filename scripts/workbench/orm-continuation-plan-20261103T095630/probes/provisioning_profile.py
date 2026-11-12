"""Perfil de una instalación nueva: qué migración y qué sentencia cuesta.

Diseño: ``designs/provisioning-cost-profile.md``.

Uso (con ``DB_NAME`` apuntando a una base desechable YA creada, con la
tabla de caché creada):

    DB_NAME=<base> DJANGO_SETTINGS_MODULE=config.settings.development \
        PYTHONPATH=src python provisioning_profile.py <salida>

Escribe ``<salida>/migrations.tsv`` (una fila por migración),
``<salida>/phases.tsv`` (arranque, migraciones, carga de datos) y
``<salida>/slow_statements.tsv`` (las sentencias de más de 0.5 s).

Las envolturas viven sólo en este proceso; el producto no cambia.
"""
import csv
import re
import sys
import time
from collections import Counter
from contextlib import contextmanager
from pathlib import Path

import django
from django.core import management
from django.core.management.commands import migrate as migrate_command
from django.db import connection
from django.db.migrations import migration as migration_module

CLASSES = (
    ('drop_constraint', re.compile(r'^ALTER TABLE .* DROP CONSTRAINT', re.S)),
    ('add_fk', re.compile(
        r'^ALTER TABLE .* ADD CONSTRAINT .* FOREIGN KEY', re.S)),
    ('add_constraint', re.compile(r'^ALTER TABLE .* ADD CONSTRAINT', re.S)),
    ('rename_column', re.compile(r'^ALTER TABLE .* RENAME COLUMN', re.S)),
    ('alter_column', re.compile(r'^ALTER TABLE .* ALTER COLUMN', re.S)),
    ('add_column', re.compile(r'^ALTER TABLE .* ADD COLUMN', re.S)),
    ('create_index', re.compile(r'^CREATE (UNIQUE )?INDEX', re.S)),
    ('drop_index', re.compile(r'^DROP INDEX', re.S)),
    ('create_table', re.compile(r'^CREATE TABLE', re.S)),
    ('dml', re.compile(r'^(INSERT|UPDATE|DELETE)', re.S)),
    ('select', re.compile(r'^(SELECT|WITH)', re.S)),
)


def classify(sql):
    text = sql.lstrip()
    for name, pattern in CLASSES:
        if pattern.match(text):
            return name
    return 'other'


class Recorder:
    """Acumula las sentencias en el bucket de la migración o fase activa."""

    def __init__(self):
        self.bucket = 'boot'
        self.stats = {}
        self.slow = []

    def current(self):
        return self.stats.setdefault(self.bucket, {
            'sql_seconds': 0.0, 'statements': 0, 'rows': 0,
            'classes': Counter()})

    def __call__(self, execute, sql, params, many, context):
        began = time.monotonic()
        try:
            return execute(sql, params, many, context)
        finally:
            elapsed = time.monotonic() - began
            entry = self.current()
            kind = classify(sql)
            entry['sql_seconds'] += elapsed
            entry['statements'] += 1
            entry['classes'][kind] += 1
            if kind == 'dml':
                rowcount = getattr(context['cursor'], 'rowcount', -1)
                entry['rows'] += max(rowcount, 0)
            if elapsed > 0.5:
                self.slow.append((self.bucket, kind, round(elapsed, 3),
                                  ' '.join(sql.split())[:300]))

    @contextmanager
    def into(self, bucket):
        previous, self.bucket = self.bucket, bucket
        try:
            yield
        finally:
            self.bucket = previous


def main(out_dir):
    began_boot = time.monotonic()
    django.setup()
    boot_seconds = time.monotonic() - began_boot
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    recorder = Recorder()
    walls = {}
    operations = {}

    original_apply = migration_module.Migration.apply

    def timed_apply(self, project_state, schema_editor, collect_sql=False):
        key = f'{self.app_label}.{self.name}'
        operations[key] = Counter(type(op).__name__ for op in self.operations)
        began = time.monotonic()
        with recorder.into(key):
            try:
                return original_apply(self, project_state, schema_editor,
                                      collect_sql)
            finally:
                walls[key] = time.monotonic() - began

    original_emit = migrate_command.emit_post_migrate_signal

    def timed_emit(*args, **kwargs):
        began = time.monotonic()
        with recorder.into('post_migrate'):
            try:
                return original_emit(*args, **kwargs)
            finally:
                walls['post_migrate'] = time.monotonic() - began

    migration_module.Migration.apply = timed_apply
    migrate_command.emit_post_migrate_signal = timed_emit
    began = time.monotonic()
    with connection.execute_wrapper(recorder):
        with recorder.into('migrate_outside_apply'):
            management.call_command('migrate', interactive=False, verbosity=0)
    total = time.monotonic() - began

    columns = ['migration', 'operations', 'operation_types', 'wall_seconds',
               'sql_seconds', 'python_seconds', 'statements', 'rows',
               'drop_constraint', 'add_fk', 'add_constraint', 'create_index',
               'drop_index', 'rename_column', 'alter_column', 'add_column',
               'create_table', 'dml', 'select', 'other']
    with open(out / 'migrations.tsv', 'w', newline='') as handle:
        writer = csv.writer(handle, delimiter='\t')
        writer.writerow(columns)
        for key, wall in sorted(walls.items(), key=lambda kv: -kv[1]):
            entry = recorder.stats.get(key, {'sql_seconds': 0.0,
                                             'statements': 0, 'rows': 0,
                                             'classes': Counter()})
            ops = operations.get(key, Counter())
            writer.writerow([
                key, sum(ops.values()),
                ','.join(f'{name}:{count}'
                         for name, count in ops.most_common()),
                round(wall, 3), round(entry['sql_seconds'], 3),
                round(wall - entry['sql_seconds'], 3),
                entry['statements'], entry['rows'],
                *(entry['classes'].get(name, 0) for name in columns[8:])])

    applied = sum(wall for key, wall in walls.items() if key != 'post_migrate')
    with open(out / 'phases.tsv', 'w', newline='') as handle:
        writer = csv.writer(handle, delimiter='\t')
        writer.writerow(['phase', 'wall_seconds', 'sql_seconds', 'statements'])
        writer.writerow(['boot', round(boot_seconds, 3), '', ''])
        sql_applied = sum(entry['sql_seconds'] for key, entry
                          in recorder.stats.items() if key in walls
                          and key != 'post_migrate')
        writer.writerow(['migrations_apply', round(applied, 3),
                         round(sql_applied, 3), ''])
        for bucket in ('post_migrate', 'migrate_outside_apply'):
            entry = recorder.stats.get(bucket)
            writer.writerow([bucket, round(walls.get(bucket, 0.0), 3),
                             round(entry['sql_seconds'], 3) if entry else 0,
                             entry['statements'] if entry else 0])
        writer.writerow(['migrate_total', round(total, 3), '', ''])

    with open(out / 'slow_statements.tsv', 'w', newline='') as handle:
        writer = csv.writer(handle, delimiter='\t')
        writer.writerow(['bucket', 'class', 'seconds', 'sql'])
        writer.writerows(sorted(recorder.slow, key=lambda row: -row[2]))
    print(f'migrate_total={total:.1f}s migrations={len(walls)} '
          f'boot={boot_seconds:.1f}s')


if __name__ == '__main__':
    main(sys.argv[1])
