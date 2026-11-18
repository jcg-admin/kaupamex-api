"""Re-clasifica las filas «propias» del censo de ``BaseModel``.

El censo original (``basemodel_adoption_census.py``) buscó la contraparte
sólo en ``odoo19c``. Esta sonda mide cada fila ``own-name``/``no-name`` de
``outputs/basemodel-adoption-census.tsv`` contra los cuatro alias de
``scripts/reference_roots.py`` y contra la procedencia que declara el puerto
en su propio archivo.

Columnas: ``app_label``, ``class``, ``_name``, ``bucket``, ``alias`` (el
primero que declara el mismo ``_name``, o ``-``), ``reference_file``,
``provenance`` (los alias o repositorios que cita el módulo del puerto, o
``-``).

Uso (sin base de datos)::

    PYTHONPATH=src DJANGO_SETTINGS_MODULE=config.settings.testing \\
        .venv/bin/python <este archivo> <census.tsv>

*Métrica:* ``_name`` literal en los ``.py`` de cada árbol, y citas de
procedencia en el texto del módulo del puerto.
*Ciega a:* una contraparte cuyo ``_name`` difiera del nuestro y que el
puerto no cite; y a un repositorio de terceros que ningún alias cubre (la
columna ``provenance`` lo recoge si el puerto lo nombra).
"""
import csv
import importlib
import inspect
import os
import pathlib
import re
import sys

import django
from django.apps import apps

NAME_RE = re.compile(r"^\s+_name\s*=\s*['\"]([a-z0-9_.]+)['\"]", re.M)
CITE_RE = re.compile(
    r"odoo1[89][ce]:|app-odoo-1[89]|server-tools-1[89]|odoo\.enterprise"
    r"|odoo19-enterprise|app_auto_backup")


def declarations(root):
    """``_name`` → primer archivo del árbol que lo declara."""
    found = {}
    for path in sorted(pathlib.Path(root).rglob('*.py')):
        for name in NAME_RE.findall(path.read_text(errors='ignore')):
            found.setdefault(name, str(path.relative_to(root)))
    return found


def main(census):
    django.setup()
    roots = importlib.import_module('reference_roots')
    trees = {alias: declarations(roots.tree(alias))
             for alias in ('odoo19c', 'odoo19e', 'odoo18c', 'odoo18e')}
    by_class = {(m._meta.app_label, m.__name__): m for m in apps.get_models()}
    writer = csv.writer(sys.stdout, delimiter='\t', lineterminator='\n')
    writer.writerow(['app_label', 'class', '_name', 'bucket', 'alias',
                     'reference_file', 'provenance'])
    with open(census, newline='') as handle:
        for row in csv.DictReader(handle, delimiter='\t'):
            if row['bucket'] == 'reference-name':
                continue
            name = row['_name']
            alias, ref = '-', '-'
            for key, found in trees.items():
                if name in found:
                    alias, ref = key, found[name]
                    break
            model = by_class.get((row['app_label'], row['class']))
            text = (pathlib.Path(inspect.getfile(model)).read_text()
                    if model else '')
            cites = sorted(set(CITE_RE.findall(text))) or ['-']
            writer.writerow([row['app_label'], row['class'], name,
                             row['bucket'], alias, ref, ','.join(cites)])


if __name__ == '__main__':
    sys.path[:0] = [str(pathlib.Path('scripts').resolve()),
                    str(pathlib.Path('src').resolve())]
    os.environ.setdefault('DJANGO_SETTINGS_MODULE',
                          'config.settings.testing')
    main(sys.argv[1])
