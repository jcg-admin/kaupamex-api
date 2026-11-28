"""Las 93 políticas de borrado de Django que destruyen lo que la fuente
conserva o protege.

Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
delete-policy-contract-tests.md``. Población: ``outputs/
fk_reference_ondelete.tsv`` del mismo banco (odoo-tools ``abe4040ec1``),
filas donde la fuente declara ``set null`` o ``restrict`` y Django
``CASCADE`` (o declaraba, para las ya corregidas de ``CORRECTED``).

Tres planos: el atributo de cada fila (``xfail`` estricto mientras difiera),
el borrado por el ORM en dos representantes (lo observado hoy y el contrato
de la fuente) y el borrado en SQL, que no cascada.
"""
import csv
import pathlib

import pytest
from django.apps import apps
from django.db import connection, models, transaction

from addons.base.models.ir_actions import IrActionsActions, IrActionsTodo
from addons.base.models.res_device import ResDeviceLog
from addons.stock.models import (StockLocation, StockPickingType,
                                 StockRoute, StockRule)

_MATRIX = (pathlib.Path(__file__).resolve().parents[3] / 'scripts'
           / 'workbench' / 'orm-continuation-plan-20261103T095630'
           / 'outputs' / 'fk_reference_ondelete.tsv')

#: Filas ya corregidas: su caso corre sin ``xfail`` y tiene que pasar. Cada
#: entrada cita la unidad que la corrigió.
CORRECTED = {
    # designs/stock-quant-restrict-ondelete.md
    'stock.StockQuant.product', 'stock.StockQuant.location',
    'stock.StockQuant.lot',
    # designs/country-and-todo-restrict-ondelete.md
    'base.ResCountryState.country', 'base_address_extended.ResCity.country_id',
    'base.IrActionsTodo.action_id',
    # designs/product-lot-bom-restrict-ondelete.md
    'stock.StockLot.product', 'mrp.MrpBom.product_tmpl_id',
    # designs/hr-workorder-restrict-ondelete.md
    'hr_work_entry.HrWorkEntry.employee', 'hr_work_entry.HrWorkEntry.version',
    'hr_work_entry.HrUserWorkEntryEmployee.employee',
    'mrp.MrpWorkorder.production',
    # designs/fleet-restrict-ondelete.md
    'fleet.FleetVehicleOdometer.vehicle',
    'fleet.FleetVehicleAssignationLog.vehicle',
    # designs/new-line-recompute-flow.md
    'purchase.PurchaseOrderLine.company_id',
    # designs/restrict-ondelete-non-company.md (tramo A)
    'stock.StockRule.location_dest',
    'sale_timesheet.ProjectSaleLineEmployeeMap.project',
    'sale_timesheet.ProjectSaleLineEmployeeMap.employee',
    'account.AccountFiscalPositionAccount.account_src',
    'account.AccountFiscalPositionAccount.account_dest',
    # designs/restrict-ondelete-payment-method-line.md (tramo B)
    'account.AccountPaymentMethodLine.payment_method',
    'account.AccountPaymentMethodLine.journal',
    # designs/set-null-ondelete-block-d.md (bloque D, 44 filas)
    'account.AccountBankStatement.company',
    'account.AccountBankStatement.journal',
    'account.AccountFiscalPositionAccount.company',
    'account.AccountJournalGroup.company',
    'account.AccountLockException.user',
    'account.AccountMove.company',
    'account.AccountMoveLine.company_id',
    'account.AccountPaymentTerm.company',
    'account.AccountReconcileModelLine.company',
    'account.AccountReportColumn.report',
    'account.AccountTaxRepartitionLine.company',
    'base.IrActionsServer.crud_model_id',
    'base.IrActionsServer.link_field_id',
    'base.IrActionsServer.sequence_id',
    'base.IrActionsServer.update_related_model_id',
    'base.IrDemoFailure.wizard',
    'base.IrSequence.company',
    'base.ResCurrencyRate.company',
    'base.ResDeviceLog.user',
    'base.ServerActionHistoryWizard.action',
    'mail.MailAlias.alias_parent_model',
    'mrp.MrpBom.product',
    'product.ProductCombo.company_id',
    'product.ProductComboItem.company_id',
    'product.ProductPricelist.company_id',
    'product.ProductSupplierinfo.company_id',
    'product.ProductSupplierinfo.product_id',
    'product.ProductSupplierinfo.purchase_requisition_line',
    'product.ProductTemplate.company_id',
    'product.ProductUom.company_id',
    'sales_team.CrmTeam.company_id',
    'stock.StockLocation.company',
    'stock.StockMove.picking',
    'stock.StockMove.scrap',
    'stock.StockMoveLine.lot',
    'stock.StockMoveLine.move',
    'stock.StockMoveLine.picking',
    'stock.StockPackage.company',
    'stock.StockPackageType.company',
    'stock.StockQuant.company',
    'stock.StockRoute.company',
    'stock.StockRule.company',
    'stock.StockRule.warehouse',
    'stock.StockStorageCategory.company',
    # designs/restrict-ondelete-block-f.md (bloque F, 23 filas)
    'account.AccountBankStatementLine.company',
    'account.AccountFiscalPosition.company',
    'account.AccountGroup.company',
    'account.AccountJournal.company',
    'account.AccountLockException.company',
    'account.AccountPayment.company',
    'account.AccountReconcileModel.company',
    'account.AccountReportExternalValue.company',
    'account.AccountTax.company',
    'account.AccountTaxGroup.company',
    'account_edi_proxy_client.AccountEdiProxyUser.company_id',
    'analytic.AccountAnalyticLine.company',
    'purchase.PurchaseOrder.company_id',
    'purchase_requisition.PurchaseRequisition.company',
    'sale.SaleOrder.company',
    'stock.StockMoveLine.company',
    'stock.StockPackageHistory.company',
    'stock.StockPickingType.company',
    'stock.StockPutawayRule.company',
    'stock.StockRule.picking_type',
    'stock.StockWarehouse.company',
    'stock.StockWarehouseOrderpoint.company',
    'website.Website.company',
    # designs/set-null-hr-version-employee.md
    'hr.HrVersion.employee',
    # designs/project-unlink-deletes-tasks.md
    'project.ProjectTask.project',
}

#: Política de Django que corresponde al ``ondelete`` de la fuente.
_EXPECTED = {
    'set null': (models.SET_NULL,),
    'restrict': (models.PROTECT, models.RESTRICT),
}


def _destructive_rows():
    with _MATRIX.open(newline='') as handle:
        for row in csv.DictReader(handle, delimiter='\t'):
            kind = row['reference_ondelete'].split(' (')[0]
            ident = f"{row['django_field']}.{row['field']}"
            if kind in _EXPECTED and (row['django_policy'] == 'CASCADE'
                                      or ident in CORRECTED):
                marks = () if ident in CORRECTED else pytest.mark.xfail(
                    strict=True, reason=(
                        f"{kind} -> CASCADE "
                        f"(odoo19c: {row['reference_field']})"))
                yield pytest.param(row, kind, id=ident, marks=marks)


_ROWS = list(_destructive_rows())


def test_the_population_is_the_measured_one():
    """93 filas: 48 ``set null`` y 45 ``restrict`` (42 por defecto y 3
    explícitas). Eran 96 hasta aplicar la regla de los transitorios
    (``odoo19c: odoo/orm/fields_relational.py:274-282``): tres Many2one
    obligatorios de transitorios son ``cascade`` en la fuente. Si la matriz
    cambia, este conteo lo dice antes que nadie."""
    kinds = [param.values[1] for param in _ROWS]
    assert (len(kinds), kinds.count('set null'),
            kinds.count('restrict')) == (93, 48, 45)


@pytest.mark.parametrize('row, kind', _ROWS)
def test_the_django_policy_matches_the_source_ondelete(row, kind):
    model = apps.get_model(row['django_field'])
    field = model._meta.get_field(row['field'])
    assert field.remote_field.on_delete in _EXPECTED[kind]


# --- ORM: dos representantes, uno por familia ------------------------------

@pytest.mark.django_db
def test_deleting_a_user_keeps_its_device_logs(user):
    log = ResDeviceLog.objects.create(session_identifier='probe-session',
                                      user=user)
    type(user).objects.filter(pk=user.pk).delete()
    log.refresh_from_db()
    assert log.user_id is None


@pytest.fixture
def picking_type():
    return StockPickingType.objects.create(name='Recepciones',
                                           code='incoming')


def _rule_using(picking_type):
    return StockRule.objects.create(
        name='Regla', action=StockRule.ACTION_PULL,
        route=StockRoute.objects.create(name='Ruta'),
        location_dest=StockLocation.objects.create(name='WH/Stock',
                                                   usage='internal'),
        picking_type=picking_type)


@pytest.mark.django_db
def test_deleting_a_picking_type_with_rules_is_refused(picking_type):
    rule = _rule_using(picking_type)
    with pytest.raises(models.ProtectedError):
        StockPickingType.objects.filter(pk=picking_type.pk).delete()
    assert StockRule.objects.filter(pk=rule.pk).exists()


# --- PostgreSQL: el DELETE crudo no cascada ---------------------------------

@pytest.mark.django_db
def test_a_raw_delete_of_an_action_leaves_the_step_in_place():
    """``ir_actions`` no admite clave foránea: la heredan cinco tablas y
    una FK hacia ella no vería sus filas, así que la fuente no la crea
    (``odoo19c: odoo/orm/fields_relational.py:313-314``). La política de
    borrado de ``IrActionsTodo.action_id`` vive sólo en el camino ORM —el
    caso de la matriz—, y un DELETE en SQL del padre no cascada al paso:
    lo deja apuntando a un id que ya no existe, como en la fuente."""
    action = IrActionsActions.objects.create(
        name='probe', type='ir.actions.actions')
    wizard_step = IrActionsTodo.objects.create(action_id=action)
    table = IrActionsActions._meta.db_table
    with transaction.atomic():
        with connection.cursor() as cr:
            cr.execute('SET CONSTRAINTS ALL IMMEDIATE')
            cr.execute(f'DELETE FROM {table} WHERE id = %s', [action.pk])
    assert IrActionsTodo.objects.filter(
        pk=wizard_step.pk, action_id=action.pk).exists()
