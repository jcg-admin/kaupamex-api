"""EXPERIMENTAL: censo de claves foráneas por política de borrado.

Medición exploratoria escrita antes de cerrar Search Existing: no es
autoridad, ni producto, ni evidencia de aceptación por sí sola. Solo lee.
"""
import collections
import importlib

import django


def main():
    django.setup()
    apps = importlib.import_module('django.apps').apps
    models = importlib.import_module('django.db.models')
    policy = collections.Counter()
    declared = collections.Counter()
    many2many = collections.Counter()
    crossed = collections.Counter()
    examples = collections.defaultdict(list)
    for model in apps.get_models(include_auto_created=False):
        if not model._meta.managed:
            continue
        for field in model._meta.local_fields:
            if not (isinstance(field, models.ForeignKey)
                    and field.db_constraint):
                continue
            on_delete = field.remote_field.on_delete.__name__
            ondelete = getattr(field, 'ondelete', None) or '-'
            policy[on_delete] += 1
            declared[ondelete] += 1
            key = (ondelete, on_delete)
            crossed[key] += 1
            if len(examples[key]) < 2:
                examples[key].append(f'{model._meta.label}.{field.name}')
        for field in model._meta.local_many_to_many:
            through = field.remote_field.through._meta
            many2many['auto' if through.auto_created else 'explicit'] += 1
    print('on_delete de Django:', dict(policy.most_common()))
    print('ondelete de Odoo declarado:', dict(declared.most_common()))
    print('Many2many:', dict(many2many))
    print('cruce (ondelete Odoo, on_delete Django):')
    for key, count in crossed.most_common():
        print(' ', key, count, examples[key])


if __name__ == '__main__':
    main()
