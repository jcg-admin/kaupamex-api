#!/usr/bin/env python3
"""Por qué vía llega cada miembro de ``BaseModel`` a un modelo concreto.

H-API-1145 midió ``issubclass(model, orm.models.BaseModel)`` y concluyó sobre
contratos. Esa sonda sólo ve una de las vías por las que un miembro llega a un
modelo. Ésta resuelve, para cada nombre que la clase ``BaseModel`` de la
referencia declara y para cada modelo concreto, **qué clase del MRO lo
define**, y lo clasifica:

``inheritance``
    lo define ``orm.models.BaseModel`` y el modelo hereda de ella.
``mixin``
    lo define una clase de ``src/orm`` distinta de ``BaseModel`` y de la
    ``Model`` de Django (los mixins que adopta ``TimeStampedModel``).
``patch``
    lo define ``django.db.models.Model``, pero el cuerpo vive en nuestro
    ``src/``: lo colgamos nosotros sobre la clase de Django.
``production``
    lo define cualquier otra clase nuestra: el propio modelo o un mixin de
    addon (``MailActivityMixin``, ``UtmMixin``).
``django``
    lo define Django con su propio cuerpo: homónimo, no contrato.
``object``
    lo trae ``object``.
``delegation``
    no está en la clase, pero sí en la clase del queryset de su manager por
    defecto, con cuerpo nuestro.
``absent``
    ninguna de las anteriores.

Mide PRESENCIA y VÍA. No mide comportamiento: un miembro presente puede no
cumplir el contrato. Eso lo deciden las pruebas de comportamiento.

Uso, desde ``src/``::

    eval "$(python3 ../scripts/reference_roots.py --env)"
    PYTHONPATH=. DJANGO_SETTINGS_MODULE=config.settings.testing \\
        ../.venv/bin/python "$BENCH/probes/channel_census.py" \\
        "$ODOO19C/odoo/orm/models.py" "$BENCH/outputs"
"""
import ast
import collections
import importlib
import inspect
import json
import pathlib
import sys

import django

REPRESENTATIVE = (
    'crm.lead', 'res.partner', 'sale.order', 'account.move',
    'product.template', 'stock.picking', 'res.users', 'ir.attachment',
)


def reference_members(models_py):
    """Nombres de función que el cuerpo de ``class BaseModel`` declara."""
    tree = ast.parse(pathlib.Path(models_py).read_text())
    base = next(node for node in tree.body
                if isinstance(node, ast.ClassDef) and node.name == 'BaseModel')
    return sorted({node.name for node in base.body
                   if isinstance(node, (ast.FunctionDef,
                                        ast.AsyncFunctionDef))})


def body_file(value):
    """Archivo del cuerpo de un atributo de clase, o ``None``."""
    for candidate in (value, getattr(value, '__func__', None),
                      getattr(value, 'fget', None),
                      getattr(value, 'func', None)):
        if candidate is None:
            continue
        try:
            return inspect.getsourcefile(inspect.unwrap(candidate))
        except TypeError:
            continue
    return None


def classify(model, name, ours, django_model, base_model):
    for klass in model.__mro__:
        if name not in klass.__dict__:
            continue
        if klass is object:
            return 'object', 'object'
        if klass is base_model:
            return 'inheritance', 'orm.models.BaseModel'
        source = body_file(klass.__dict__[name]) or ''
        label = f'{klass.__module__}.{klass.__qualname__}'
        if klass is django_model:
            return ('patch' if source.startswith(ours) else 'django'), label
        module_file = inspect.getsourcefile(klass) or ''
        if not module_file.startswith(ours):
            return 'django', label
        if klass.__module__.split('.')[0] == 'orm':
            return 'mixin', label
        return 'production', label
    queryset = model._default_manager.get_queryset()
    for klass in type(queryset).__mro__:
        if name in klass.__dict__:
            source = body_file(klass.__dict__[name]) or ''
            if source.startswith(ours):
                return 'delegation', f'{klass.__module__}.{klass.__qualname__}'
            break
    return 'absent', ''


def main(models_py, outputs):
    django.setup()
    # Los modelos sólo existen tras ``django.setup()``: se resuelven después,
    # por ``importlib``, no con un ``import`` dentro de la función.
    apps = importlib.import_module('django.apps').apps
    django_models = importlib.import_module('django.db.models')
    BaseModel = importlib.import_module('orm.models').BaseModel

    repo = pathlib.Path('.').resolve().parent
    # El ``.venv`` vive dentro del repo: la raíz entera confundía el cuerpo de
    # Django con el nuestro. Sólo cuentan ``src/`` y ``addons/``.
    ours = (str(repo / 'src') + '/', str(repo / 'addons') + '/')
    names = reference_members(models_py)
    concrete = [model for model in apps.get_models()
                if not model._meta.abstract and not model._meta.proxy]
    production = [model for model in concrete
                  if not model._meta.app_label.startswith('test_')]

    per_name = {name: collections.Counter() for name in names}
    representative = {}
    for model in production:
        reference_name = model.__dict__.get('_name')
        row = {}
        for name in names:
            channel, owner = classify(model, name, ours,
                                      django_models.Model, BaseModel)
            per_name[name][channel] += 1
            row[name] = (channel, owner)
        if reference_name in REPRESENTATIVE:
            representative[reference_name] = row

    out = pathlib.Path(outputs)
    with (out / 'channels_by_name.tsv').open('w') as handle:
        channels = ('inheritance', 'mixin', 'patch', 'delegation',
                    'production', 'django', 'object', 'absent')
        handle.write('name\t' + '\t'.join(channels) + '\n')
        for name in names:
            handle.write(name + '\t' + '\t'.join(
                str(per_name[name][c]) for c in channels) + '\n')
    with (out / 'representative.tsv').open('w') as handle:
        handle.write('model\tname\tchannel\towner\n')
        for reference_name in REPRESENTATIVE:
            for name, (channel, owner) in representative.get(
                    reference_name, {}).items():
                handle.write(f'{reference_name}\t{name}\t{channel}\t{owner}\n')
    summary = {
        'reference_members': len(names),
        'concrete_models': len(concrete),
        'production_models': len(production),
        'production_subclassing_basemodel': sum(
            issubclass(m, BaseModel) for m in production),
        'representative_found': sorted(representative),
        'reach_by_channel': {
            channel: sum(1 for name in names if per_name[name][channel])
            for channel in ('inheritance', 'mixin', 'patch', 'delegation',
                            'production', 'django', 'object')
        },
        'names_absent_on_every_production_model': sum(
            1 for name in names
            if per_name[name]['absent'] == len(production)),
    }
    (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main(*sys.argv[1:3])
