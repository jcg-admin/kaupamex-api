"""Los cómputos que cada ``save()`` invoca, cruzados con el registro.

Por cada modelo cuyo ``save()`` (o su ``_compute_stored_fields``) invoca
métodos ``_compute_*``, lista qué campos los declaran como calculados y su
clase: ``pre`` (precompute), ``ro`` (readonly sin precompute) o ``rw``
(editable). Sólo lee el registro: no abre la base.

Uso, desde la raíz del repo::

    PYTHONPATH=src .venv/bin/python <este archivo>
"""
import ast
import importlib
import inspect
import os
import textwrap

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
django.setup()
apps = importlib.import_module('django.apps').apps
model_field_registry = importlib.import_module(
    'orm.models').model_field_registry


def compute_calls(function):
    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    return sorted({
        node.func.attr for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == 'self'
        and node.func.attr.startswith('_compute')})


def field_class(field):
    if getattr(field, 'precompute', False):
        return 'pre'
    return 'ro' if getattr(field, 'readonly', False) else 'rw'


def main():
    for model in apps.get_models():
        save = model.__dict__.get('save')
        if save is None:
            continue
        methods = compute_calls(save)
        if '_compute_stored_fields' in methods:
            methods += compute_calls(model._compute_stored_fields)
        if not methods:
            continue
        declared = {}
        for field in model_field_registry(model).values():
            method = getattr(field, 'compute', None)
            if method in methods:
                declared.setdefault(method, set()).add(
                    (field.name, field_class(field)))
        print('\t'.join([
            model._meta.label, f'methods={len(set(methods))}',
            f'declared={len(declared)}',
            '; '.join(f'{method}:{sorted(values)}'
                      for method, values in sorted(declared.items()))]))


if __name__ == '__main__':
    main()
