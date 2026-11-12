"""Matriz de los modelos con calculados almacenados.

Imprime, por modelo, si hereda de ``BaseModel`` (vía ORM de alta), cuántos
calculados almacenados declara, cuántos son precompute o readonly, cuántos
grupos de cómputo tienen más de un campo y en cuántos archivos de
``tests/`` aparece su clase. Sólo lee: no escribe en la base ni en disco.

Uso, desde la raíz del repo::

    PYTHONPATH=src .venv/bin/python <este archivo>
"""
import importlib
import os
import subprocess

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
django.setup()
# Los modelos sólo se pueden importar con el registro ya poblado: se cargan
# por llamada, después de ``django.setup()``.
apps = importlib.import_module('django.apps').apps
orm_models = importlib.import_module('orm.models')
BaseModel = orm_models.BaseModel
model_field_registry = orm_models.model_field_registry


def stored_computes(model):
    found = {}
    for field in model_field_registry(model).values():
        if getattr(field, 'compute', None) and getattr(field, 'store', False):
            found[id(field)] = field
    return list(found.values())


def test_files(name):
    out = subprocess.run(['git', 'grep', '-l', name, '--', 'tests/'],
                         capture_output=True, text=True, check=False)
    return len(out.stdout.split())


def main():
    rows = []
    for model in apps.get_models():
        computed = stored_computes(model)
        if not computed:
            continue
        groups = {}
        for field in computed:
            groups.setdefault(field.compute, []).append(field)
        rows.append((
            model._meta.label,
            'BaseModel' if issubclass(model, BaseModel) else 'Django',
            len(computed),
            sum(1 for f in computed if getattr(f, 'precompute', False)),
            sum(1 for f in computed if getattr(f, 'readonly', False)),
            sum(1 for group in groups.values() if len(group) > 1),
            test_files(model.__name__),
        ))
    print('label\tbase\tstored_computes\tprecompute\treadonly\t'
          'groups_gt1\ttest_files')
    for row in sorted(rows):
        print('\t'.join(map(str, row)))


if __name__ == '__main__':
    main()
