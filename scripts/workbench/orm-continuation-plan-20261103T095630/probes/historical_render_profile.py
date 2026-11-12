"""Perfil de un renderizado del estado histórico completo.

Renderiza una vez para calentar, y perfila el segundo renderizado con
cProfile; imprime las funciones por tiempo acumulado. No abre la base.

Uso, desde la raíz del repo::

    PYTHONPATH=src .venv/bin/python <este archivo>
"""
import cProfile
import importlib
import io
import os
import pstats

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
django.setup()
apps = importlib.import_module('django.apps').apps
state_module = importlib.import_module('django.db.migrations.state')


def main():
    state = state_module.ProjectState.from_apps(apps)
    state.apps
    state.__dict__.pop('apps', None)
    profiler = cProfile.Profile()
    profiler.enable()
    state.apps
    profiler.disable()
    out = io.StringIO()
    pstats.Stats(profiler, stream=out).sort_stats('cumulative').print_stats(28)
    print(out.getvalue())


if __name__ == '__main__':
    main()
