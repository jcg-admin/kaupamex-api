"""Clasifica cada modelo del registro de Django por su identidad contractual.

Sonda de la unidad ``model-identity-contract-0397`` (diseño
``designs/model-identity-contract.md``). Extiende
``basemodel_counterpart_census.py``: aquélla re-clasificaba sólo las filas
«propias» del censo de ``BaseModel``; ésta recorre **todo**
``apps.get_models(include_auto_created=True)`` y asigna una de cinco
categorías, con la señal que la decide en su propia columna.

Categorías:

1. ``reference-name`` — declara un ``_name`` propio que ``odoo19c`` declara.
2. ``reference-unnamed`` — la fuente lo modela y aquí no lo declara (o lo
   declara distinto): su tabla es la ``_table`` de un modelo de ``odoo19c``,
   o su módulo cita el archivo de la fuente que declara ese ``_name``.
3. ``kaupamex`` — modelo de un addon de Kaupamex sin contraparte en la fuente.
   La columna ``participation`` recoge la evidencia de que participa en el ORM
   (``BaseModel``, filas de ACL o reglas sembradas, literal citado fuera de
   su archivo); sin evidencia queda ``kaupamex-unproven``.
4. ``django-internal`` — app que no es un addon de este árbol
   (``django.contrib``, ``rest_framework_simplejwt``…).
5. ``infrastructure`` — tabla intermedia creada por Django
   (``auto_created``) o modelo explícito de relación cuya tabla es una tabla
   ``*_rel`` de la fuente.

Uso (sin base de datos)::

    PYTHONPATH=src:scripts DJANGO_SETTINGS_MODULE=config.settings.testing \\
        .venv/bin/python <este archivo> > outputs/model-identity-census.tsv

*Métrica:* ``_name`` y ``_table`` literales en los ``.py`` de ``odoo19c``;
nombres de tabla de relación explícitos (``relation=`` o segundo argumento
posicional de ``Many2many``) y los implícitos derivados como lo hace la
fuente; el ``_name`` y la tabla de cada modelo de aquí; el módulo de su app.
*Ciega a:* una contraparte con tabla y nombre distintos que el puerto no
cite; las tablas de relación implícitas cuyo comodelo no se resuelva por
literal; y la participación que sólo se da por valores construidos en
tiempo de ejecución.
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
TABLE_RE = re.compile(r"^\s+_table\s*=\s*['\"]([a-z0-9_]+)['\"]", re.M)
CLASS_RE = re.compile(r"^class\s+\w+\(([^)]*)\):", re.M)
RELATION_RE = re.compile(
    r"Many2many\(\s*(?:comodel_name=)?['\"][a-z0-9_.]+['\"]\s*,\s*"
    r"(?:relation=)?['\"]([a-z0-9_]+)['\"]")
RELATION_KW_RE = re.compile(r"relation\s*=\s*['\"]([a-z0-9_]+)['\"]")
CITE_RE = re.compile(r"odoo19c:\s*(?:addons/)?([a-z0-9_/]+\.py)")


def reference_models(root):
    """``_name`` → (archivo, tabla) y el conjunto de tablas de relación."""
    names, relations = {}, set()
    for path in sorted(pathlib.Path(root).rglob('*.py')):
        if '/tests/' in str(path):
            continue
        text = path.read_text(errors='ignore')
        rel = str(path.relative_to(root))
        for block in re.split(r"(?m)^class\s+", text)[1:]:
            name = NAME_RE.search('    ' + block)
            if not name:
                continue
            table = TABLE_RE.search('    ' + block)
            names.setdefault(name.group(1), (
                rel, table.group(1) if table else
                name.group(1).replace('.', '_')))
        relations.update(RELATION_RE.findall(text))
        relations.update(RELATION_KW_RE.findall(text))
    return names, relations


def addon_roots():
    base = pathlib.Path('.').resolve()
    return (base / 'addons', base / 'src' / 'addons')


def own_participation(model, label, name, texts, base_model):
    """La evidencia de que un modelo propio participa en el ORM."""
    found = []
    if issubclass(model, base_model):
        found.append('basemodel')
    own_file = inspect.getfile(model)
    needles = {label} | ({name} if name else set())
    for path, text in texts:
        if path == own_file:
            continue
        if any(needle in text for needle in needles):
            kind = ('security' if '/security/' in path else
                    'data' if '/data/' in path or '/migrations/' in path
                    else 'code')
            if kind not in found:
                found.append(kind)
    return found


def main():
    django.setup()
    base_model = importlib.import_module('orm.models').BaseModel
    ref_root = importlib.import_module('reference_roots').tree('odoo19c')
    ref_names, ref_relations = reference_models(ref_root)
    ref_by_table = {table: name for name, (_f, table) in ref_names.items()}
    ref_files = {f: name for name, (f, _t) in ref_names.items()}
    roots = addon_roots()
    texts = []
    for root in roots:
        for path in root.rglob('*'):
            if path.suffix in ('.py', '.csv', '.xml') and \
                    '/tests/' not in str(path):
                texts.append((str(path), path.read_text(errors='ignore')))
    writer = csv.writer(sys.stdout, delimiter='\t', lineterminator='\n')
    writer.writerow(['category', 'label', 'db_table', '_name',
                     'reference_name', 'signal', 'participation'])
    for model in sorted(apps.get_models(include_auto_created=True),
                        key=lambda m: m._meta.label):
        meta = model._meta
        label, table = meta.label, meta.db_table
        name = model.__dict__.get('_name')
        module_file = pathlib.Path(inspect.getfile(model)).resolve()
        own_app = any(root in module_file.parents for root in roots)
        participation = '-'
        if meta.auto_created:
            category, ref, signal = 'infrastructure', '-', 'auto_created'
        elif not own_app:
            category, ref, signal = 'django-internal', '-', 'app-outside-tree'
        elif name and name in ref_names:
            category, ref, signal = 'reference-name', name, '_name'
        elif table in ref_by_table:
            category, ref = 'reference-unnamed', ref_by_table[table]
            signal = 'db_table'
        elif table in ref_relations:
            category, ref = 'infrastructure', '-'
            signal = 'reference-rel-table'
        else:
            text = module_file.read_text(errors='ignore')
            cited = [ref_files[c] for c in CITE_RE.findall(text)
                     if c in ref_files]
            class_doc = inspect.getdoc(model) or ''
            cited_class = [ref_files[c] for c in CITE_RE.findall(class_doc)
                           if c in ref_files]
            if cited_class:
                category, ref = 'reference-unnamed', cited_class[0]
                signal = 'class-citation'
            else:
                found = own_participation(
                    model, label, name, texts, base_model)
                participation = ','.join(found) or '-'
                category = 'kaupamex' if found else 'kaupamex-unproven'
                ref = '-'
                signal = ('module-citation:' + cited[0]) if cited else 'none'
        writer.writerow([category, label, table, name or '-', ref, signal,
                         participation])


if __name__ == '__main__':
    sys.path[:0] = [str(pathlib.Path('scripts').resolve()),
                    str(pathlib.Path('src').resolve())]
    os.environ.setdefault('DJANGO_SETTINGS_MODULE',
                          'config.settings.testing')
    main()
