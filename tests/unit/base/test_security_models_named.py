"""Los modelos que nombran los datos de seguridad de ``hr`` llevan ``_name``.

``hr/security/ir.model.access.csv`` nombra ``resource.model_resource_*`` y
``hr_security.xml`` crea ``res.groups.privilege``. Un modelo sin ``_name``
no tiene XML-ID de modelo ni nombre en el cargador
(``designs/module-install-cycle.md``, L4c). Atributos de la fuente:
``odoo19c: addons/resource/models/*.py`` y
``odoo/addons/base/models/res_groups_privilege.py:5-7``.
"""
import pytest

from addons.base.models import IrModelData
from addons.base.models.ir_model import IrModel
from orm.registry import model_by_name

pytestmark = pytest.mark.django_db

NAMES = {
    'resource': ('resource.resource', 'resource.calendar',
                 'resource.calendar.attendance', 'resource.calendar.leaves'),
}


def test_the_resource_models_get_their_xmlid():
    IrModelData.objects.filter(module='resource',
                               name__startswith='model_').delete()
    IrModel._reflect_models({'resource'}, module='resource')
    written = set(IrModelData.objects.filter(
        module='resource', name__startswith='model_').values_list(
            'name', flat=True))
    assert {'model_' + name.replace('.', '_')
            for name in NAMES['resource']} <= written


def test_the_privilege_model_has_its_source_name():
    model = model_by_name('res.groups.privilege')
    assert model._meta.db_table == 'res_groups_privilege'
    assert model._description == 'Privileges'
