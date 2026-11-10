"""Matriz de impacto de ``@api.constrains`` por modelo concreto.

Para cada método marcado en cada modelo concreto registra: la clase del
modelo (``BaseModel`` o Django), los nombres declarados, si cada nombre
resuelve a un campo, si ese campo es almacenado, y por qué vías corría
ANTES del cambio (recómputo, inverso no almacenado) y cuáles se añaden
DESPUÉS (``_create``, ``write``).

Se ejecuta con: ``cd src && DJANGO_SETTINGS_MODULE=config.settings.testing
python ../<este archivo>``. Sólo lee el registro; no escribe en la base.
"""
import csv
import importlib
import sys

import django

# Los módulos del ORM sólo se cargan con las aplicaciones listas: se piden
# después de ``django.setup()`` por llamada, no por sentencia ``import``.
django.setup()
apps = importlib.import_module('django.apps').apps
registry = importlib.import_module('orm.registry')
orm_models = importlib.import_module('orm.models')
BaseModel = orm_models.BaseModel
DefaultGetMixin = orm_models.DefaultGetMixin
RecordLoaderMixin = orm_models.RecordLoaderMixin
model_field_registry = orm_models.model_field_registry

writer = csv.writer(sys.stdout, delimiter='\t')
writer.writerow([
    'model', 'kind', 'method', 'declared', 'unresolved', 'nonstored',
    'computed_stored', 'create_path', 'write_path',
    'ran_before', 'runs_after'])
for model in sorted(apps.get_models(), key=lambda m: m._meta.label):
    methods = registry.constraint_methods(model)
    if not methods:
        continue
    fields = model_field_registry(model)
    kind = 'BaseModel' if issubclass(model, BaseModel) else 'django'
    create_path = ('DefaultGetMixin._create'
                   if issubclass(model, DefaultGetMixin) else 'none')
    write_path = ('BaseModel.write' if kind == 'BaseModel' else
                  'RecordLoaderMixin.write'
                  if issubclass(model, RecordLoaderMixin) else 'none')
    for method in methods:
        declared = tuple(method._constrains)
        unresolved = [n for n in declared if n not in fields]
        resolved = [fields[n] for n in declared if n in fields]
        nonstored = [f.name for f in resolved
                     if not getattr(f, 'store', True)]
        computed_stored = [f.name for f in resolved
                           if getattr(f, 'compute', None)
                           and getattr(f, 'store', True)]
        before = []
        if computed_stored:
            before.append('recompute')
        if any(getattr(f, 'inverse', None) and not getattr(f, 'store', True)
               for f in resolved):
            before.append('create-inverse')
        after = list(before)
        if create_path != 'none':
            after.append('create')
        if write_path != 'none':
            after.append('write')
        writer.writerow([
            model._meta.label, kind, method.__name__, ','.join(declared),
            ','.join(unresolved), ','.join(nonstored),
            ','.join(computed_stored), create_path, write_path,
            ','.join(before) or 'never', ','.join(after) or 'never'])
