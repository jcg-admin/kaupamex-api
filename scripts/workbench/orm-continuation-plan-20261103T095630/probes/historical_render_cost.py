"""Reloj de pared de un renderizado del estado histórico completo.

``ProjectState.from_apps(apps).apps`` sobre todo el registro, tres veces;
con ``skip`` no instala los descriptores del ORM en modelos de
``StateApps``, para medir cuánto pesa esa parte. No abre la base.

Uso, desde la raíz del repo::

    PYTHONPATH=src .venv/bin/python <este archivo> base|skip
"""
import importlib
import os
import sys
import time

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
django.setup()
apps = importlib.import_module('django.apps').apps
state_module = importlib.import_module('django.db.migrations.state')
orm_fields = importlib.import_module('orm.fields')


def skip_descriptors():
    original = orm_fields._install_field_descriptor

    def install(field, cls):
        if isinstance(cls._meta.apps, state_module.StateApps):
            return None
        return original(field, cls)

    orm_fields._install_field_descriptor = install


def main(mode):
    if mode == 'skip':
        skip_descriptors()
    state = state_module.ProjectState.from_apps(apps)
    start = time.perf_counter()
    rendered = None
    for _ in range(3):
        state.__dict__.pop('apps', None)
        rendered = state.apps
    seconds = (time.perf_counter() - start) / 3
    print(mode, 'models', len(rendered.get_models()),
          'seconds per render', round(seconds, 3))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'base')
