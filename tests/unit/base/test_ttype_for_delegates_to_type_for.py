"""``ir.model.fields.ttype_for`` publica el ``type`` de la referencia.

La reflexión de la referencia guarda ``'ttype': field.type``
(``odoo19c: odoo/addons/base/models/ir_model.py:1173``), y el puerto tiene
el porte de ``Field.type`` en ``orm.fields.type_for``, cuyo docstring dice
que ``ttype_for`` le delega. No lo hacía: con su propio mapa reflejaba los
``Selection`` como ``char`` y un ``Selection`` dependiente de empresa como
``json`` (H-API-1164, TASK-API-0501).

Los tipos esperados salen de la referencia: ``update_field_type``
(``ir_actions.py:667``), ``terms_type`` (``sale_order.py:317``) y
``default_applicability`` (``analytic_plan.py:77``) son ``Selection``;
``Serialized.type`` es ``'serialized'``
(``addons/base_sparse_field/models/fields.py:80``).
"""

import pytest
from django.apps import apps

from addons.base.models.ir_model import IrModelFields
from orm.fields import type_for


def _field(label, name):
    return apps.get_model(label)._meta.get_field(name)


@pytest.mark.parametrize('label, name, expected', [
    ('base.IrActionsServer', 'update_field_type', 'selection'),
    ('sale.SaleOrder', 'terms_type', 'selection'),
    ('analytic.AccountAnalyticPlan', 'default_applicability', 'selection'),
    ('base_sparse_field.SparseFieldsTest', 'data', 'serialized'),
])
def test_both_owners_publish_the_reference_type(label, name, expected):
    field = _field(label, name)
    assert (IrModelFields.ttype_for(field), type_for(field)) == (
        expected, expected)
