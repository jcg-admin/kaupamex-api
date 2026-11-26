"""``properties.base.definition`` es ``BaseModel``, con su regla y su ACL.

``class PropertiesBaseDefinition(models.Model)``
(``odoo19c: odoo/addons/base/models/properties_base_definition.py:6-67``), la
fila de ACL de ``group_system`` (``ir.model.access.csv:147``) y la regla
``properties.base.definition: system all access``
(``base_security.xml:256-261``). Diseño:
``designs/basemodel-adoption-properties-base-definition.md``.
"""

import models
import pytest

from addons.base.models.ir_model import (STATE_BASE, IrModel, IrModelAccess,
                                         IrModelData, IrModelFields)
from addons.base.models.ir_rule import IrRule
from addons.base.models.properties_base_definition import (
    PropertiesBaseDefinition)
from addons.base.security.ir_model_access import _ACCESS
from exceptions import AccessError
from orm import fields_properties
from orm.environments import Environment, sudo

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def test_it_is_basemodel_with_the_source_field_type():
    assert issubclass(PropertiesBaseDefinition, models.BaseModel)
    field = PropertiesBaseDefinition._meta.get_field('properties_definition')
    assert isinstance(field, fields_properties.PropertiesDefinition)


def test_the_three_qualified_csv_rows_are_derived():
    labels = {(name, label) for name, label, _group, _perms in _ACCESS}
    assert {
        ('access_res_device', 'base.ResDevice'),
        ('access_res_device_log', 'base.ResDeviceLog'),
        ('access_properties_base_definition',
         'base.PropertiesBaseDefinition'),
    } <= labels
    assert IrModelAccess.objects.filter(
        name='access_properties_base_definition').exists()


def test_the_system_rule_is_seeded():
    rule = IrRule.objects.get(
        name='properties.base.definition: system all access')
    assert rule.domain_force == "[(1, '=', 1)]"
    system = IrModelData._xmlid_to_res_id('base.group_system',
                                          raise_if_not_found=True)
    assert list(rule.groups.values_list('pk', flat=True)) == [system]


def _properties_field(name):
    ir_model, _ = IrModel.objects.get_or_create(
        model='base.Probe', defaults={'name': 'base.Probe'})
    return IrModelFields.objects.create(
        model_id=ir_model, model='base.Probe', name=name, ttype='properties',
        state=STATE_BASE, field_description='Propiedades')


def test_writing_the_target_field_is_refused():
    """≙ ``write`` (``:43-46``): reapuntar la definición es ``AccessError``;
    cambiar el esquema no."""
    field, other = _properties_field('pbd_a'), _properties_field('pbd_b')
    with sudo():
        definitions = Environment(uid=1)['properties.base.definition']
        definition = definitions.create({'properties_field_id': field.pk})
        with pytest.raises(AccessError):
            definition.write({'properties_field_id': other.pk})
        definition.write({'properties_definition': [
            {'name': 'a', 'type': 'char'}]})
        assert definition.properties_definition == [
            {'name': 'a', 'type': 'char'}]
