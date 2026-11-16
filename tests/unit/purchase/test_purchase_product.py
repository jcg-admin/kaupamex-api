"""Lo que ``purchase`` cuelga en ``product`` y la cantidad en la unidad del
producto de la línea de compra.

≙ ``odoo19c: addons/purchase/models/product.py`` (``ProductTemplate``,
``ProductProduct``, ``ProductSupplierinfo``),
``purchase_order_line.py:24,484-490`` (``product_uom_qty``) y
``account_invoice.py:530,556-560`` (``purchase_line_warn_msg`` de la línea
de factura). Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/
designs/purchase-product.md``.
"""
import datetime
import importlib
from decimal import Decimal

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import connection
from django.utils import timezone

from addons.base.models import IrModelData, ResCompany, ResPartner
from addons.uom.models import Uom
from exceptions import UserError
from orm.environments import Environment, get_transaction, sudo
from orm.migration_operations import ComputeStoredFields
from orm.domains import to_q
from orm.registry import MODELS_BY_NAME
from orm.utils import SUPERUSER_ID
from tests.factories.product_factory import make_product

pytestmark = pytest.mark.django_db

ORDER = 'purchase.order'
LINE = 'purchase.order.line'


@pytest.fixture(autouse=True)
def _as_superuser():
    with sudo():
        yield


def _product(name, **values):
    """Un producto con unidad: ``uom_id`` es obligatorio en la plantilla de
    la fuente; ``make_product`` no la pone si no se le da."""
    values.setdefault('uom', Uom.objects.create(name='Unidad ' + name,
                                                relative_factor=1.0))
    return make_product(name=name, **values)


def _order(product, qty=3, uom=None, approved=True, days_ago=0):
    company = ResCompany.objects.create(name='Compras PP %s' % qty)
    vendor = ResPartner.objects.create(name='Proveedor PP')
    [order] = MODELS_BY_NAME[ORDER].create(
        [{'partner_id': vendor.pk, 'company_id': company.pk,
          'currency_id': company.currency_id}])
    # Una línea de producto lleva unidad: la fuente lo exige con un CHECK
    # (``purchase_order_line.py:99``).
    uom = uom or product.uom
    values = {'order_id': order.id, 'name': 'Insumo', 'product_qty': qty,
              'price_unit': Decimal('10.00'), 'product_id': product.pk,
              'product_uom_id': uom.pk}
    MODELS_BY_NAME[LINE].create([values])
    if approved:
        when = timezone.now() - datetime.timedelta(days=days_ago)
        MODELS_BY_NAME[ORDER].objects.filter(pk=order.id).update(
            state='purchase', date_approve=when)
    get_transaction().flush()
    return order


def _fresh(model, pk):
    return MODELS_BY_NAME[model].objects.get(pk=pk) if '.' in model else None


# --- product_uom_qty de la línea (purchase_order_line.py:484-490) ---------

def test_the_line_quantity_in_the_product_unit_converts_the_line_unit():
    unit = Uom.objects.create(name='Units PP', relative_factor=1.0)
    dozen = Uom.objects.create(name='Dozen PP', relative_factor=12,
                               relative_uom_id=unit)
    product = _product('Insumo PP docena', uom=unit)
    order = _order(product, qty=2, uom=dozen)
    [line] = MODELS_BY_NAME[LINE].objects.filter(order_id=order.id)
    assert line.product_uom_qty == 24


def test_in_the_product_unit_the_quantity_is_copied():
    product = _product('Insumo PP misma')
    order = _order(product, qty=5)
    [line] = MODELS_BY_NAME[LINE].objects.filter(order_id=order.id)
    assert line.product_uom_qty == 5


# --- purchase_method (product.py:14-19,22-28) -----------------------------

def test_a_service_is_billed_on_ordered_quantities():
    product = _product('Servicio PP', type='service')
    assert product.product_tmpl.purchase_method == 'purchase'


def test_a_good_is_billed_on_received_quantities():
    product = _product('Bien PP', type='consu')
    assert product.product_tmpl.purchase_method == 'receive'


def test_changing_the_type_recomputes_the_policy():
    template = _product('Cambio PP', type='consu').product_tmpl
    template.write({'type': 'service'})
    assert template.purchase_method == 'purchase'


# --- purchased_product_qty (product.py:30-32,69-82) -----------------------

def test_the_variant_sums_the_approved_lines_of_the_last_year():
    product = _product('Comprado PP')
    _order(product, qty=4)
    _order(product, qty=6, days_ago=30)
    _order(product, qty=50, days_ago=400)
    _order(product, qty=70, approved=False)
    assert product.purchased_product_qty == 10


def test_the_template_sums_its_variants():
    product = _product('Plantilla PP')
    _order(product, qty=7)
    assert product.product_tmpl.purchased_product_qty == 7


# --- is_in_purchase_order (product.py:64-67,84-105) -----------------------

def test_only_the_products_of_the_context_order_are_in_it():
    inside = _product('Dentro PP')
    outside = _product('Fuera PP')
    order = _order(inside, approved=False)
    model = type(inside)
    with Environment('default', SUPERUSER_ID, {'order_id': order.id}):
        assert model.objects.get(pk=inside.pk).is_in_purchase_order is True
        assert model.objects.get(pk=outside.pk).is_in_purchase_order is False
        found = set(model.objects.filter(to_q(
            [('is_in_purchase_order', 'in', [True])], model))
            .values_list('pk', flat=True))
    assert inside.pk in found and outside.pk not in found


def test_without_an_order_in_context_nothing_is_in_it():
    product = _product('Sin orden PP')
    _order(product, approved=False)
    with Environment('default', SUPERUSER_ID, {}):
        assert type(product).objects.get(
            pk=product.pk).is_in_purchase_order is False


# --- _update_uom y _trigger_uom_warning (product.py:116-140) --------------

def test_the_unit_cannot_change_once_another_unit_was_bought():
    unit = Uom.objects.create(name='Units PP2', relative_factor=1.0)
    dozen = Uom.objects.create(name='Dozen PP2', relative_factor=12,
                               relative_uom_id=unit)
    product = _product('Unidad PP', uom=unit)
    _order(product, qty=1, uom=dozen)
    with pytest.raises(UserError):
        product._update_uom(dozen.pk)


def test_changing_the_unit_rewrites_the_purchase_lines():
    unit = Uom.objects.create(name='Units PP3', relative_factor=1.0)
    other = Uom.objects.create(name='Pack PP3', relative_factor=1.0)
    product = _product('Reescribe PP', uom=unit)
    order = _order(product, qty=1)
    product._update_uom(other.pk)
    [line] = MODELS_BY_NAME[LINE].objects.filter(order_id=order.id)
    assert line.product_uom_id_id == other.pk


def test_a_product_with_purchase_lines_warns_on_unit_change():
    product = _product('Aviso PP')
    assert product._trigger_uom_warning() is False
    _order(product, approved=False)
    assert product._trigger_uom_warning() is True


# --- _get_filtered_supplier (product.py:150-153) --------------------------

def test_the_order_company_filters_the_sellers():
    product = _product('Proveedores PP')
    order = _order(product, approved=False)
    other = ResCompany.objects.create(name='Otra PP')
    supplierinfo = MODELS_BY_NAME['product.supplierinfo'] \
        if 'product.supplierinfo' in MODELS_BY_NAME else None
    seller_model = supplierinfo or __import__(
        'addons.product.models', fromlist=['ProductSupplierinfo']
    ).ProductSupplierinfo
    mine = seller_model.objects.create(
        partner=ResPartner.objects.create(name='Mío PP'),
        product_tmpl=product.product_tmpl, company=order.company_id, price=1)
    seller_model.objects.create(
        partner=ResPartner.objects.create(name='Ajeno PP'),
        product_tmpl=product.product_tmpl, company=other, price=1)
    sellers = seller_model._get_filtered_supplier(
        product.product_tmpl.seller_ids.all(), other, product,
        {'order_id': order})
    assert [seller.pk for seller in sellers] == [mine.pk]


# --- purchase_line_warn_msg (product.py:20; account_invoice.py:556-560) ----

def _bill_line(product):
    company = ResCompany.objects.create(name='Factura PP')
    journal = MODELS_BY_NAME['account.journal'].objects.create(
        name='Compras', code='BPP', type='purchase', company=company) \
        if 'account.journal' in MODELS_BY_NAME else None
    move_model = MODELS_BY_NAME['account.move']
    move = move_model.objects.create(
        date=timezone.now().date(), journal=journal, company=company,
        move_type='in_invoice')
    return MODELS_BY_NAME['account.move.line'].objects.create(
        move=move, product_id=product, debit=Decimal('1.00'),
        credit=Decimal('0.00'))


def _user(*xmlids):
    user = get_user_model().objects.create_user(
        login='warn-%s' % len(xmlids), password=None, name='warn')
    for xmlid in xmlids:
        user.group_ids.add(IrModelData.ref(xmlid))
    return user


def test_the_bill_line_shows_the_product_warning_with_the_group():
    template = _product('Avisado PP').product_tmpl
    template.write({'purchase_line_warn_msg': 'Revisar lote'})
    line = _bill_line(template.product_variant_ids.first())
    user = _user('purchase.group_warning_purchase')
    with Environment('default', user.pk, {}):
        assert line.purchase_line_warn_msg == 'Revisar lote'


def test_without_the_group_the_warning_is_empty():
    template = _product('Sin aviso PP').product_tmpl
    template.write({'purchase_line_warn_msg': 'Revisar lote'})
    line = _bill_line(template.product_variant_ids.first())
    user = _user()
    with Environment('default', user.pk, {}):
        assert line.purchase_line_warn_msg == ''


# --- migraciones sobre filas existentes -----------------------------------

def _run_compute(module, operation_index=-1):
    operation = importlib.import_module(module).Migration.operations[
        operation_index]
    assert isinstance(operation, ComputeStoredFields)
    with connection.schema_editor() as editor:
        operation.code(apps, editor)


def _column(table, column, pk):
    with connection.cursor() as cursor:
        cursor.execute(f'SELECT {column} FROM {table} WHERE id = %s', [pk])
        return cursor.fetchone()[0]


def test_migration_0016_fills_the_existing_lines():
    unit = Uom.objects.create(name='Units MIG', relative_factor=1.0)
    dozen = Uom.objects.create(name='Dozen MIG', relative_factor=12,
                               relative_uom_id=unit)
    order = _order(_product('Migrada PP', uom=unit), qty=3, uom=dozen)
    [line] = MODELS_BY_NAME[LINE].objects.filter(order_id=order.id)
    MODELS_BY_NAME[LINE].objects.filter(pk=line.pk).update(
        product_uom_qty=None)
    _run_compute('addons.purchase.migrations.0016_line_product_uom_qty')
    assert _column('purchase_order_line', 'product_uom_qty', line.pk) == 36


def test_migration_0022_fills_the_existing_templates():
    template = _product('Servicio MIG', type='service').product_tmpl
    get_transaction().flush()
    type(template).objects.filter(pk=template.pk).update(
        purchase_method='receive')
    _run_compute('addons.product.migrations.0022_purchase_fields')
    assert _column('product_template', 'purchase_method',
                   template.pk) == 'purchase'
