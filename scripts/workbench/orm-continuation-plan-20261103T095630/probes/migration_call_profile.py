"""Perfil de llamadas de UNA migración, sin base ni instalación completa.

Diseño: ``designs/provisioning-cost-profile.md`` (sección «Causa»).

``sqlmigrate`` recorre el mismo camino que ``migrate`` —estado del proyecto,
``state_forwards`` y ``database_forwards`` de cada operación— en modo de
recolección de SQL, sin escribir nada. Se perfila con ``cProfile`` y se
separa el costo de construir el estado previo del de aplicar la migración.

Uso:
    DJANGO_SETTINGS_MODULE=config.settings.testing PYTHONPATH=src \\
        python migration_call_profile.py <app> <migración> <salida>

Escribe ``<salida>/<app>.<migración>.prof`` (para ``pstats``) y
``<salida>/<app>.<migración>.txt`` con las 40 funciones de más tiempo
acumulado y la pared de cada fase.
"""
import cProfile
import io
import pstats
import sys
import time
from pathlib import Path

import django
from django.db import connection
from django.db.migrations.loader import MigrationLoader


def main(app_label, migration_name, out_dir):
    django.setup()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    loader = MigrationLoader(connection, replace_migrations=False)
    target = (app_label, migration_name)
    migration = loader.get_migration(app_label, migration_name)
    previous = [parent.key for parent in loader.graph.node_map[target].parents]

    began = time.monotonic()
    state = loader.project_state(previous, at_end=True)
    state.apps  # renderiza el estado previo, como lo haría migrate
    pre_state_seconds = time.monotonic() - began

    profiler = cProfile.Profile()
    began = time.monotonic()
    profiler.enable()
    with connection.schema_editor(collect_sql=True, atomic=False) as editor:
        migration.apply(state, editor, collect_sql=True)
    profiler.disable()
    apply_seconds = time.monotonic() - began

    stem = f'{app_label}.{migration_name}'
    profiler.dump_stats(str(out / f'{stem}.prof'))
    buffer = io.StringIO()
    stats = pstats.Stats(profiler, stream=buffer).sort_stats('cumulative')
    stats.print_stats(40)
    header = (f'migration={stem} operations={len(migration.operations)}\n'
              f'pre_state_seconds={pre_state_seconds:.2f}\n'
              f'apply_seconds={apply_seconds:.2f}\n\n')
    (out / f'{stem}.txt').write_text(header + buffer.getvalue())
    print(header.strip())


if __name__ == '__main__':
    main(*sys.argv[1:4])
