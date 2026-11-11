"""EXPERIMENTAL: el ondelete de la fuente frente al de cada FK del árbol.

Medición exploratoria escrita antes de cerrar Search Existing: no es
autoridad, ni producto, ni evidencia de aceptación por sí sola. Solo lee:
el árbol de referencia por AST y la base de pruebas por pg_constraint.

Uso: python fk_reference_ondelete.py <raíz odoo19c> <salida.tsv>
"""
import ast
import collections
import csv
import importlib
import pathlib
import sys

import django

THIRD = ('django.', 'rest_framework')
POLICY = {'CASCADE': 'cascade', 'SET_NULL': 'set null',
          'PROTECT': 'restrict', 'RESTRICT': 'restrict'}


def literal(node):
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError):
        return None


def reference_fields(root):
    """``{(modelo, campo): (ondelete efectivo, archivo:línea)}``."""
    found = {}
    files = list(root.glob('addons/*/models/*.py'))
    files += list(root.glob('odoo/addons/*/models/*.py'))
    for path in files:
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for cls in (n for n in tree.body if isinstance(n, ast.ClassDef)):
            name = inherit = None
            for stmt in cls.body:
                if (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1
                        and isinstance(stmt.targets[0], ast.Name)):
                    if stmt.targets[0].id == '_name':
                        name = literal(stmt.value)
                    elif stmt.targets[0].id == '_inherit':
                        inherit = literal(stmt.value)
            model = name or (inherit if isinstance(inherit, str)
                             else (inherit or [None])[0])
            if not isinstance(model, str):
                continue
            for stmt in cls.body:
                call = getattr(stmt, 'value', None)
                if not (isinstance(stmt, ast.Assign)
                        and isinstance(call, ast.Call)
                        and getattr(call.func, 'attr', None) == 'Many2one'
                        and isinstance(stmt.targets[0], ast.Name)):
                    continue
                kwargs = {k.arg: literal(k.value) for k in call.keywords}
                ondelete = kwargs.get('ondelete')
                if kwargs.get('company_dependent'):
                    ondelete = 'company_dependent'
                elif ondelete is None:
                    ondelete = ('restrict' if kwargs.get('required')
                                else 'set null') + ' (defecto)'
                found[(model, stmt.targets[0].id)] = (
                    ondelete, f'{path.relative_to(root)}:{stmt.lineno}')
    return found


def main(root, out):
    django.setup()
    apps = importlib.import_module('django.apps').apps
    db = importlib.import_module('django.db')
    models = importlib.import_module('django.db.models')
    reference = reference_fields(pathlib.Path(root))
    # Sin ``_name`` declarado, el modelo se reconoce por su tabla: es la
    # regla ``_table = _name.replace('.', '_')`` que vigila
    # ``orm.registry.check_table_matches_name``.
    by_table = {name.replace('.', '_'): name for name, _ in reference}
    with db.connection.cursor() as cr:
        cr.execute("""
            SELECT c1.relname, a1.attname, fk.confdeltype, fk.condeferrable
              FROM pg_constraint fk
              JOIN pg_class c1 ON fk.conrelid = c1.oid
              JOIN pg_attribute a1 ON a1.attrelid = c1.oid
                                  AND fk.conkey[1] = a1.attnum
             WHERE fk.contype = 'f'""")
        constraint = {(t, c): (d, df) for t, c, d, df in cr.fetchall()}
    rows, summary = [], collections.Counter()
    for model in apps.get_models():
        if model.__module__.startswith(THIRD) or not model._meta.managed:
            continue
        model_name = getattr(model, '_name', None) or by_table.get(
            model._meta.db_table)
        for field in model._meta.local_fields:
            if not (isinstance(field, models.ForeignKey)
                    and field.db_constraint):
                continue
            policy = field.remote_field.on_delete.__name__
            attribute = getattr(field, 'ondelete', None) or '-'
            ref = (reference.get((model_name, field.column))
                   or reference.get((model_name, field.name))
                   or reference.get((model_name, field.name + '_id')))
            ref_ondelete = ref[0].replace(' (defecto)', '') if ref else None
            deltype, deferrable = constraint.get(
                (model._meta.db_table, field.column), ('-', '-'))
            attribute_ok = ref_ondelete is None or attribute == ref_ondelete
            policy_ok = (ref_ondelete is None
                         or POLICY.get(policy) == ref_ondelete)
            if ref is None:
                verdict = 'sin contraparte en la fuente'
            elif ref_ondelete == 'company_dependent':
                verdict = 'dependiente de empresa en la fuente (sin FK)'
            elif attribute_ok and policy_ok:
                verdict = 'coherente'
            elif policy_ok:
                verdict = 'divergencia de atributo'
            elif attribute_ok:
                verdict = 'divergencia de política'
            else:
                verdict = 'divergencia de atributo y de política'
            summary[verdict] += 1
            rows.append([
                model_name or '-', ref[1] if ref else '-',
                ref[0] if ref else '-', model._meta.label, field.name,
                attribute, policy, deltype, deferrable, verdict])
    with open(out, 'w', newline='', encoding='utf-8') as handle:
        writer = csv.writer(handle, delimiter='\t', lineterminator='\n')
        writer.writerow([
            'reference_model', 'reference_field', 'reference_ondelete',
            'django_field', 'field', 'ondelete_attribute',
            'django_policy', 'confdeltype', 'deferrable', 'verdict'])
        writer.writerows(rows)
    print('FK medidas:', len(rows))
    for verdict, count in summary.most_common():
        print(f'  {verdict}: {count}')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
