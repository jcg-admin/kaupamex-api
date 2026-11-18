"""Censo de los modelos concretos que no adoptan ``RecordLoaderMixin``.

Unidad ``record-loader-universality-0485``. Escribe un TSV por stdout:
``app_label``, ``class``, ``_name``, ``class_kind`` y ``base``.

- ``framework``: apps de Django y de SimpleJWT, sin contraparte posible.
- ``reference-name``: declara un ``_name`` que la referencia también
  declara (``odoo19c: addons`` y ``odoo/addons``).
- ``own-name``: declara un ``_name`` que la referencia no tiene.
- ``no-name``: no declara ``_name``; puede tener contraparte igual (p. ej.
  ``analytic.AccountAnalyticPlan`` ≙ ``account.analytic.plan``), así que
  este cubo no prueba ausencia de contraparte.

Uso (sin base de datos; sólo ``django.setup()``)::

    PYTHONPATH=src DJANGO_SETTINGS_MODULE=config.settings.testing \\
        .venv/bin/python <este archivo> <raíz de odoo19c>

*Métrica:* clases de ``apps.get_models()`` sin el mixin, por cubo.
*Ciega a:* la contraparte de un modelo sin ``_name``.
"""
import importlib
import pathlib
import re
import sys

import django
from django.apps import apps

FRAMEWORK = {'admin', 'auth', 'contenttypes', 'sessions', 'token_blacklist'}
NAME_RE = re.compile(r"^\s+_name\s*=\s*['\"]([a-z0-9_.]+)['\"]", re.M)


def reference_names(root):
    names = set()
    for sub in ('addons', 'odoo/addons'):
        for path in pathlib.Path(root, sub).rglob('*.py'):
            names.update(NAME_RE.findall(path.read_text(errors='ignore')))
    return names


def main(root):
    django.setup()
    # ``orm.models`` exige el registro de apps poblado: se carga después de
    # ``django.setup()`` por llamada, no por sentencia (patrón de
    # ``delete_paths.py``).
    orm_models = importlib.import_module('orm.models')
    BaseModel = orm_models.BaseModel
    RecordLoaderMixin = orm_models.RecordLoaderMixin
    ref = reference_names(root)
    print('app_label\tclass\t_name\tclass_kind\tbase')
    rows = []
    for model in apps.get_models():
        meta = model._meta
        if meta.abstract or meta.proxy or issubclass(model, RecordLoaderMixin):
            continue
        name = getattr(model, '_name', None) or ''
        if meta.app_label in FRAMEWORK:
            kind = 'framework'
        elif not name:
            kind = 'no-name'
        else:
            kind = 'reference-name' if name in ref else 'own-name'
        base = 'BaseModel' if issubclass(model, BaseModel) else 'django'
        rows.append((meta.app_label, model.__name__, name or '-', kind, base))
    for row in sorted(rows):
        print('\t'.join(row))


if __name__ == '__main__':
    main(sys.argv[1])
