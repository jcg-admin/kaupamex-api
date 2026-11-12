"""Matriz por campo de los calculados almacenados.

Una fila por campo calculado almacenado de cada modelo del registro, con:
método de cómputo, dependencias declaradas, precompute, clase de protección
en alta (``_protected_on_create``), vía de alta, momento del cálculo,
control que lo verifica, anulación y hueco restante. Las tres últimas
columnas salen de ``CONTROLS``, que nombra los controles existentes; un
campo sin entrada queda como hueco declarado. Sólo lee el registro: no abre
la base.

Uso, desde la raíz del repo::

    PYTHONPATH=src .venv/bin/python <este archivo>
"""
import importlib
import os

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
django.setup()
# Los modelos sólo se pueden importar con el registro ya poblado.
apps = importlib.import_module('django.apps').apps
orm_models = importlib.import_module('orm.models')
registry = importlib.import_module('orm.registry')
BaseModel = orm_models.BaseModel
model_field_registry = orm_models.model_field_registry

#: (etiqueta, campo) → (control, anulación). Los controles viven en
#: ``tests/unit/orm/test_create_protection.py`` (CP),
#: ``tests/unit/sale_timesheet/test_employee_map_computes.py`` (EM) y
#: ``tests/integration/test_orm/test_creation_marks_on_alias.py`` (AL).
CP = 'tests/unit/orm/test_create_protection.py'
EM = 'tests/unit/sale_timesheet/test_employee_map_computes.py'
AL = 'tests/integration/test_orm/test_creation_marks_on_alias.py'
CONTROLS = {
    ('test_orm.TestOrmSharedCompute', 'start'): (
        f'{CP} grupo (Django y ORM), asignación previa al save; {AL}',
        'grupo, terna, asignación, recómputo en sitio, sudo, alias'),
    ('test_orm.TestOrmSharedCompute', 'end'): (
        f'{CP} grupo (Django y ORM); {AL}', 'grupo, alias'),
    ('test_orm.TestOrmSharedCompute', 'name'): (
        f'{CP} marcado único vía _create', 'ORM_CREATE_INSERTING'),
    ('sale_timesheet.ProjectSaleLineEmployeeMap', 'price_unit'): (
        f'{EM}; {CP} readonly recalculado', 'not readonly'),
    ('sale_timesheet.ProjectSaleLineEmployeeMap', 'currency'): (
        f'{EM} moneda real desde la línea', 'line.currency_id'),
    ('sale_timesheet.ProjectSaleLineEmployeeMap', 'cost'): (
        f'{EM} sigue al empleado y deja de seguirlo; {CP} editable',
        '-'),
    ('sale_timesheet.ProjectSaleLineEmployeeMap', 'is_cost_changed'): (
        f'{EM} costo escrito a mano', '-'),
    ('sale.SaleOrderLine', 'price_subtotal'): (
        f'{CP} precompute protegido, sin recálculo tras el INSERT',
        'precompute en la regla'),
}

COLUMNS = ['model', 'field', 'compute_method', 'dependencies', 'precompute',
           'explicit_value_protection', 'creation_path', 'computed_when',
           'verification', 'nullification', 'remaining_gap']


def stored_computes(model):
    found = {}
    for field in model_field_registry(model).values():
        if getattr(field, 'compute', None) and getattr(field, 'store', False):
            found[id(field)] = field
    return list(found.values())


def protection(field):
    if getattr(field, 'precompute', False):
        return 'siempre (precompute)'
    if not getattr(field, 'readonly', False):
        return 'si se da (editable), con su grupo'
    return 'no (readonly): se recalcula'


def computed_when(field):
    if getattr(field, 'precompute', False):
        return 'antes del INSERT (pre_save)'
    return 'tras el INSERT (marcado de creación) y volcado'


def rows():
    for model in sorted(apps.get_models(), key=lambda m: m._meta.label):
        computed = stored_computes(model)
        label = model._meta.label
        path = ('BaseModel.create y save()' if issubclass(model, BaseModel)
                else 'save() de Django')
        for field in sorted(computed, key=lambda f: f.name):
            depends = registry.field_depends[field]
            control, nullification = CONTROLS.get(
                (label, field.name), ('-', '-'))
            gap = ('-' if control != '-'
                   else 'sin control propio del cálculo en alta')
            yield [label, field.name, field.compute,
                   ', '.join(depends) or '-',
                   'sí' if getattr(field, 'precompute', False) else 'no',
                   protection(field), path, computed_when(field),
                   control, nullification, gap]


def main():
    print('\t'.join(COLUMNS))
    for row in rows():
        print('\t'.join(str(value) for value in row))


if __name__ == '__main__':
    main()
