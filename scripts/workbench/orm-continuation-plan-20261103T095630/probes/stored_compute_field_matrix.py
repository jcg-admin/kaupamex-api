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
CB = 'tests/unit/orm/test_compute_before_insert.py'
MD = 'tests/integration/company/test_multidb_isolation.py'
FW = 'tests/unit/orm/test_flush_write_contract.py'
MC = 'tests/unit/orm/test_method_chain_depends.py'
CONTROLS = {
    ('test_orm.TestOrmSharedCompute', 'start'): (
        f'{CP} grupo (Django y ORM), asignación previa al save; {AL}; '
        f'{MD} dos bases reales',
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
        f'{CP} precompute protegido; {CB} una invocación en alta',
        'precompute en la regla; cálculo en alta de save()'),
    ('crm.CrmLead', 'won_status'): (
        f'{CB} una invocación en alta (antes 12); dependencia posterior',
        'volcado por save(); cálculo en alta de save()'),
    ('crm.CrmLead', 'team_id'): (
        f'{CB} una invocación en alta (antes 12)',
        'volcado por save(); cálculo en alta de save()'),
    ('crm.CrmLead', 'prorated_revenue'): (
        f'{CB} valor tras el volcado y recálculo al cambiar probability; '
        f'{FW} volcado sin señales, sin save() y con write_date',
        'UPDATE -> save_base (cae señales); -> save (cae señales y '
        'sobrescritura); sin Field.pre_save (cae write_date)'),
    ('sale.SaleOrderLine', 'price_tax'): (
        f'{CB} valor del mismo cálculo (_compute_amount) en alta', '-'),
    ('sale.SaleOrderLine', 'price_total'): (
        f'{CB} valor del mismo cálculo (_compute_amount) en alta', '-'),
    ('account.AccountPaymentMethodLine', 'name'): (
        f'{MC} dependencia de la base en el registro y marca de recálculo '
        'al renombrar el método',
        'get_depends sin la cadena; extensión con setattr (caen 2 cada una)'),
    ('account.AccountAccount', 'internal_group'): (
        f'{CB} una invocación en alta (antes 3)',
        'volcado por save(); cálculo en alta de save()'),
    ('account.AccountAccount', 'account_type'): (
        f'{CB} dado en alta: cero invocaciones y valor conservado',
        'cálculo en alta de save()'),
    ('account.AccountMoveLine', 'balance'): (
        f'{CB} una invocación en alta', 'la asignación cuenta como dada'),
    ('sale.SaleOrder', 'validity_date'): (
        f'{CB} una invocación en alta (pase de precompute)', '-'),
}

#: Huecos conocidos que no son falta de control, sino defecto medido.
KNOWN_GAPS = {}

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
            gap = KNOWN_GAPS.get((label, field.name)) or (
                '-' if control != '-'
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
