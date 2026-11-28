"""``module_id`` en dependencias y exclusiones; los One2many del módulo.

≙ ``odoo19c: odoo/addons/base/models/ir_module.py:295-299,1009,1074``.
Diseño: ``designs/ir-module-dependency-module-id.md``.
"""

import pytest

from addons.base.models import IrModule, IrModuleDependency, IrModuleExclusion
from orm.environments import Environment
from orm.utils import SUPERUSER_ID

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.mark.parametrize('model', [IrModuleDependency, IrModuleExclusion])
def test_the_foreign_key_keeps_the_source_name(model):
    # ``get_field`` resuelve también el ``attname`` de un campo ``module``:
    # el nombre se lee de ``field.name``.
    field = model._meta.get_field('module_id')
    assert (field.name, field.column, field.related_model) == (
        'module_id', 'module_id', IrModule)


def test_dependencies_and_exclusions_are_read_from_the_module():
    module = IrModule.objects.create(name='mid_owner', shortdesc='Owner')
    IrModuleDependency.objects.create(module_id=module, name='mid_dep')
    IrModuleExclusion.objects.create(module_id=module, name='mid_excl')
    record = Environment(uid=SUPERUSER_ID)['ir.module.module'].browse(
        module.id)
    assert record.dependencies_id.mapped('name') == ['mid_dep']
    assert record.exclusion_ids.mapped('name') == ['mid_excl']
