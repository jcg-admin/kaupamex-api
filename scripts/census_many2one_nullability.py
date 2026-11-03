#!/usr/bin/env python3
"""Censo por columna de la nulabilidad de los ``Many2one`` — H-API-1122.

La fuente resuelve ``required`` como ``False`` salvo que se declare
(``odoo19c: odoo/orm/fields_relational.py:282``); aquí un ``Many2one`` sin
``null=`` produce una columna ``NOT NULL``. Este censo cruza cada
``ForeignKey`` con columna de los modelos cargados con el ``Many2one``
homónimo que declara la referencia para el mismo modelo, y reparte cada
columna en uno de cinco cubos:

``aligned_required``
    La fuente lo declara ``required=True`` y aquí es ``NOT NULL``.
``aligned_optional``
    La fuente no lo requiere y aquí admite ``NULL``.
``required_by_omission``
    La fuente no lo requiere y aquí es ``NOT NULL``: es la divergencia de
    H-API-1122.
``relaxed``
    La fuente lo requiere y aquí admite ``NULL``.
``unmatched``
    La referencia no declara ese campo para ese modelo (un campo propio, un
    modelo propio, o un nombre que difiere).

Un ``required`` que la fuente escribe como expresión (no un literal) se
reparte en ``required_expr`` aparte: no se puede decidir sin evaluarla.

El modelo se empareja por ``_name`` cuando la clase lo declara, y si no por
su tabla: la de la fuente es ``_table`` o ``_name`` con ``.`` cambiado por
``_`` (``odoo19c: odoo/orm/model_classes.py:266``). El campo se empareja por
el ``attname`` de Django, que conserva el sufijo ``_id`` de la fuente.

*Métrica:* columnas ``ForeignKey`` concretas de los modelos cargados, por
cubo, contra las declaraciones ``fields.Many2one(...)`` de ``odoo19c``.
*Ciega a:* la nulabilidad física de la base ya migrada (mide la declaración
del modelo, no ``information_schema``), a un ``required`` que la fuente fija
fuera de la declaración del campo, y a un campo que aquí se llame distinto.

Uso::

    uv run python scripts/census_many2one_nullability.py            # cubos
    uv run python scripts/census_many2one_nullability.py --tsv F     # detalle
"""
import argparse
import ast
import collections
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'src'))
import reference_roots  # noqa: E402

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')

import django  # noqa: E402
from django.apps import apps  # noqa: E402
from django.db import models  # noqa: E402

BUCKETS = ('aligned_required', 'aligned_optional', 'required_by_omission',
           'relaxed', 'required_expr', 'unmatched')


def _literal(node):
    return node.value if isinstance(node, ast.Constant) else None


def _class_models(cls):
    """Los ``_name`` a los que contribuye una clase de la referencia."""
    names, inherits, table = None, [], None
    for stmt in cls.body:
        if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
            continue
        target = stmt.targets[0]
        if not isinstance(target, ast.Name):
            continue
        if target.id == '_name':
            names = _literal(stmt.value)
        elif target.id == '_inherit':
            if isinstance(stmt.value, ast.Constant):
                inherits = [stmt.value.value]
            elif isinstance(stmt.value, (ast.List, ast.Tuple)):
                inherits = [_literal(e) for e in stmt.value.elts]
        elif target.id == '_table':
            table = _literal(stmt.value)
    if isinstance(names, str):
        return [names], table
    return [i for i in inherits if isinstance(i, str)], table


def _many2one_required(call):
    """``True``/``False``/``'expr'`` del ``required`` de una llamada, o
    ``None`` si la declaración no tiene columna (``related``/``compute``
    sin ``store=True``)."""
    keywords = {k.arg: k.value for k in call.keywords if k.arg}
    store = keywords.get('store')
    stored = isinstance(store, ast.Constant) and store.value is True
    if ('related' in keywords or 'compute' in keywords) and not stored:
        return None
    required = keywords.get('required')
    if required is None:
        return False
    if isinstance(required, ast.Constant):
        return bool(required.value)
    return 'expr'


def reference_index(alias='odoo19c'):
    """``{(modelo, campo): {valores de required}}`` y ``{tabla: modelo}``."""
    declared = collections.defaultdict(set)
    tables = {}
    for root in reference_roots.addons_de(alias):
        for path in root.rglob('*.py'):
            if '/tests/' in str(path) or '/migrations/' in str(path):
                continue
            try:
                tree = ast.parse(path.read_text(errors='replace'))
            except SyntaxError:
                continue
            for cls in ast.walk(tree):
                if not isinstance(cls, ast.ClassDef):
                    continue
                models, table = _class_models(cls)
                if not models:
                    continue
                for model in models:
                    tables.setdefault(table or model.replace('.', '_'), model)
                for stmt in cls.body:
                    if not (isinstance(stmt, ast.Assign)
                            and len(stmt.targets) == 1
                            and isinstance(stmt.targets[0], ast.Name)
                            and isinstance(stmt.value, ast.Call)):
                        continue
                    func = stmt.value.func
                    name = getattr(func, 'attr', getattr(func, 'id', None))
                    if name != 'Many2one':
                        continue
                    required = _many2one_required(stmt.value)
                    if required is None:
                        continue
                    for model in models:
                        declared[(model, stmt.targets[0].id)].add(required)
    return declared, tables


def bucket(reference_values, null):
    if not reference_values:
        return 'unmatched'
    if 'expr' in reference_values:
        return 'required_expr'
    required = True in reference_values
    if required:
        return 'relaxed' if null else 'aligned_required'
    return 'aligned_optional' if null else 'required_by_omission'


def column_bucket(model, field, declared, tables):
    """``(nombre de la fuente, valores de required, cubo)`` de una columna."""
    name = model.__dict__.get('_name') or tables.get(model._meta.db_table)
    values = set()
    if name:
        # El ``attname`` conserva el sufijo de la fuente (``company`` →
        # ``company_id``); un campo que ya lo lleva en el nombre
        # (``group_id`` → ``group_id_id``) se empareja por el nombre.
        values = (declared.get((name, field.attname))
                  or declared.get((name, field.name)) or set())
    return name, values, bucket(values, field.null)


def consumer_columns():
    django.setup()
    for model in apps.get_models():
        if model._meta.proxy or not model._meta.managed:
            continue
        for field in model._meta.concrete_fields:
            if isinstance(field, models.ForeignKey):
                yield model, field


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--tsv', type=pathlib.Path)
    args = parser.parse_args(argv)
    reference_roots.require('odoo19c')
    declared, tables = reference_index()
    counts = collections.Counter()
    rows = []
    for model, field in consumer_columns():
        name, values, result = column_bucket(model, field, declared, tables)
        counts[result] += 1
        rows.append((result, model._meta.label, name or '-', field.attname,
                     'NULL' if field.null else 'NOT NULL',
                     ','.join(sorted(map(str, values))) or '-'))
    total = sum(counts.values())
    for name in BUCKETS:
        print(f'{name:22} {counts[name]:5}')
    print(f'{"total":22} {total:5}  (columnas ForeignKey de modelos gestionados)')
    if args.tsv:
        with args.tsv.open('w') as out:
            out.write('bucket\tmodel\tsource_name\tcolumn\tnullability\tsource_required\n')
            for row in sorted(rows):
                out.write('\t'.join(row) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
