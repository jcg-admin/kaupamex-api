"""Bloque D: borrar el destino deja la fila con la columna vacía.

Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
set-null-ondelete-block-d.md``. Un ``Many2one`` no obligatorio sin
``ondelete`` es ``set null`` (``odoo19c: odoo/orm/fields_relational.py:
274-282``). Cuatro filas cuyo destino se puede borrar sin otra guarda; la
quinta (``ResDeviceLog.user``) y el atributo de las 44 están en
``test_delete_policy_contract.py``.

*Métrica:* la fila hija leída de la base tras borrar el destino.
*Ciega a:* las filas hacia ``res.company``, cuyo borrado rehúsan otras
relaciones.
"""
import pytest
from django.apps import apps

from orm.environments import sudo

pytestmark = pytest.mark.django_db

IrSequence = apps.get_model('base', 'IrSequence')
IrActionsServer = apps.get_model('base', 'IrActionsServer')
AccountReport = apps.get_model('account', 'AccountReport')
AccountReportColumn = apps.get_model('account', 'AccountReportColumn')
ProductTemplate = apps.get_model('product', 'ProductTemplate')
ProductProduct = apps.get_model('product', 'ProductProduct')
ProductSupplierinfo = apps.get_model('product', 'ProductSupplierinfo')
MrpBom = apps.get_model('mrp', 'MrpBom')
ResPartner = apps.get_model('base', 'ResPartner')


@pytest.fixture(autouse=True)
def _as_superuser():
    with sudo():
        yield


def _delete(row):
    type(row).objects.filter(pk=row.pk).delete()


def _variant(name):
    template = ProductTemplate.objects.create(name=name)
    variant = ProductProduct.objects.filter(product_tmpl=template).first()
    return template, variant or ProductProduct.objects.create(
        product_tmpl=template)


def test_deleting_a_report_keeps_its_columns():
    report = AccountReport.objects.create(name='Informe D')
    column = AccountReportColumn.objects.create(
        name='Saldo', expression_label='balance', report=report)
    _delete(report)
    column.refresh_from_db()
    assert column.report_id is None


def test_deleting_a_sequence_keeps_the_action_that_used_it():
    sequence = IrSequence.objects.create(name='Secuencia D')
    action = IrActionsServer.objects.create(
        name='Acción D', type='ir.actions.server', state='code',
        model_name='res.partner', sequence_id=sequence)
    _delete(sequence)
    action.refresh_from_db()
    assert action.sequence_id_id is None


def test_deleting_a_variant_keeps_its_vendor_price():
    template, variant = _variant('Producto D')
    price = ProductSupplierinfo.objects.create(
        partner_id=ResPartner.objects.create(name='Proveedor D'),
        product_tmpl=template, product=variant)
    _delete(variant)
    price.refresh_from_db()
    assert price.product_id is None


def test_deleting_a_variant_keeps_its_bill_of_materials():
    template, variant = _variant('Producto BoM D')
    bom = MrpBom.objects.create(product_tmpl=template, product=variant)
    _delete(variant)
    bom.refresh_from_db()
    assert bom.product_id is None
