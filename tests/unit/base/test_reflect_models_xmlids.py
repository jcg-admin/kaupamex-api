"""``_reflect_models`` da a cada modelo del módulo su XML-ID — ≙
``odoo19c: odoo/addons/base/models/ir_model.py:462-475``::

    # update their XML id
    module = self.env.context.get('module')
    if not module:
        return
    ...
            if model._module == module:
                xml_id = model_xmlid(module, model_name)

con ``model_xmlid`` (``:63-65``) = ``'%s.model_%s' % (module,
model_name.replace('.', '_'))``. Es lo que resuelve ``model_id:id`` en el
``ir.model.access.csv`` de un módulo. Diseño:
``designs/module-install-cycle.md``, L1.
"""
import pytest
from django.apps import apps

from addons.base.models.ir_model import IrModel, IrModelData

pytestmark = pytest.mark.django_db


def _xmlid_target(module, name):
    return (IrModelData.objects.filter(module=module, name=name)
            .values_list('model', 'res_id').first())


def test_the_module_models_get_their_xmlid():
    IrModel._reflect_models({'hr'}, module='hr')
    row = IrModel.objects.get(model='hr.HrEmployee')
    assert _xmlid_target('hr', 'model_hr_employee') == (
        'base.IrModel', row.pk)


def test_without_a_module_no_xmlid_is_written():
    IrModel._reflect_models({'hr'})
    assert _xmlid_target('hr', 'model_hr_employee') is None


def test_a_model_of_another_module_is_not_named_by_this_one():
    IrModel._reflect_models({'hr', 'hr_skills'}, module='hr')
    assert _xmlid_target('hr_skills', 'model_hr_employee_skill') is None
    assert _xmlid_target('hr', 'model_hr_employee_skill') is None


def test_only_the_models_with_a_reference_name_get_an_xmlid():
    """Un modelo sin ``_name`` propio (de Django, tabla automática o con el
    nombre heredado de un mixin) no tiene nombre en la referencia del que
    derivar ``model_<nombre>``."""
    models = list(apps.get_app_config('hr').get_models(
        include_auto_created=True))
    named = {model._name for model in models if '_name' in vars(model)}
    assert len(named) < len(models), 'el control necesita un modelo sin _name'
    IrModel._reflect_models({'hr'}, module='hr')
    written = set(IrModelData.objects.filter(
        module='hr', name__startswith='model_').values_list('name', flat=True))
    assert written == {'model_' + name.replace('.', '_') for name in named}
