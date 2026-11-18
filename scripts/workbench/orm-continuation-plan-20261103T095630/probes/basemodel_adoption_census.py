"""Censo de los modelos concretos propios que no derivan de ``BaseModel``.

Unidad paraguas ``basemodel-adoption-0397`` (TASK-API-0397). Escribe un TSV
por stdout, una fila por modelo:

``app_label``, ``class``, ``_name``, ``bucket``, ``reference_file`` y
``acl_rows``.

- ``bucket``: ``reference-name`` si la referencia declara el mismo
  ``_name``; ``own-name`` si lo declara sólo este árbol; ``no-name`` si la
  clase no declara ``_name`` (puede tener contraparte igual).
- ``reference_file``: el archivo de ``odoo19c`` que declara ese ``_name``
  (el primero, en orden de ruta), o ``-``.
- ``acl_rows``: filas de ``ir.model.access.csv`` de la referencia cuyo
  ``model_id:id`` es ``model_<_name con '.' → '_'>``; la ACL que la
  adopción tiene que traer (``designs/basemodel-adoption-utm.md``).

Uso (sin base de datos; sólo ``django.setup()``)::

    PYTHONPATH=src DJANGO_SETTINGS_MODULE=config.settings.testing \\
        .venv/bin/python <este archivo> <raíz de odoo19c> <raíz del repo>

*Métrica:* clases de ``apps.get_models()`` concretas, no proxy, de apps
propias, declaradas fuera de ``tests/``, que no son ``BaseModel``.
*Ciega a:* la contraparte de un modelo sin ``_name``, y a una ACL que la
referencia declare en XML en vez de CSV.
"""
import collections
import csv
import importlib
import inspect
import pathlib
import re
import sys

import django
from django.apps import apps

FRAMEWORK = {'admin', 'auth', 'contenttypes', 'sessions', 'token_blacklist'}
NAME_RE = re.compile(r"^\s+_name\s*=\s*['\"]([a-z0-9_.]+)['\"]", re.M)


def reference_declarations(root):
    """``_name`` → primer archivo de la referencia que lo declara."""
    found = {}
    for sub in ('addons', 'odoo/addons'):
        for path in sorted(pathlib.Path(root, sub).rglob('*.py')):
            for name in NAME_RE.findall(path.read_text(errors='ignore')):
                found.setdefault(name, str(path.relative_to(root)))
    return found


def reference_acl(root):
    """``model_<x>`` → filas de ACL de la referencia que lo nombran."""
    rows = collections.Counter()
    for sub in ('addons', 'odoo/addons'):
        for path in pathlib.Path(root, sub).rglob('ir.model.access.csv'):
            with path.open(newline='', errors='ignore') as handle:
                for row in csv.DictReader(handle):
                    key = (row.get('model_id:id') or '').split('.')[-1]
                    rows[key] += 1
    return rows


def main(root, repo):
    sys.path.insert(0, str(pathlib.Path(repo, 'src')))
    django.setup()
    # Tras ``django.setup()``: el registro de apps tiene que estar poblado.
    BaseModel = importlib.import_module('orm.models').BaseModel
    for path in pathlib.Path(repo).glob('addons/*/report/*.py'):
        if path.stem != '__init__':
            importlib.import_module(
                f'addons.{path.parent.parent.name}.report.{path.stem}')
    tests = pathlib.Path(repo, 'tests').resolve()
    declared = reference_declarations(root)
    acl = reference_acl(root)
    writer = csv.writer(sys.stdout, delimiter='\t', lineterminator='\n')
    writer.writerow(['app_label', 'class', '_name', 'bucket',
                     'reference_file', 'acl_rows'])
    for model in sorted(apps.get_models(),
                        key=lambda m: (m._meta.app_label, m.__name__)):
        meta = model._meta
        if meta.abstract or meta.proxy or meta.app_label in FRAMEWORK:
            continue
        if tests in pathlib.Path(inspect.getfile(model)).resolve().parents:
            continue
        if issubclass(model, BaseModel):
            continue
        name = model.__dict__.get('_name') or ''
        if not name:
            bucket = 'no-name'
        elif name in declared:
            bucket = 'reference-name'
        else:
            bucket = 'own-name'
        writer.writerow([
            meta.app_label, model.__name__, name or '-', bucket,
            declared.get(name, '-'),
            acl.get('model_' + name.replace('.', '_'), 0) if name else 0,
        ])


if __name__ == '__main__':
    main(*sys.argv[1:3])
