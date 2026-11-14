"""Cabecera de ``purchase.order`` y ``purchase.order.line`` sobre
``BaseModel``.

≙ ``odoo19c: addons/purchase/models/purchase_order.py:21-26,78-87`` y
``purchase_order_line.py:13-22``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
purchase-order-header.md``.
"""
import pytest

from addons.account.models.account_document_import_mixin import (
    AccountDocumentImportMixin)
from addons.analytic.models.analytic_mixin import AnalyticMixin
from addons.mail.models import MailActivityMixin, MailThread
from addons.portal.models.portal_mixin import PortalMixin
from addons.product.models.product_catalog_mixin import ProductCatalogMixin
from orm.models import BaseModel
from orm.registry import MODELS_BY_NAME

pytestmark = pytest.mark.django_db


def test_the_order_is_registered_under_its_source_name():
    order = MODELS_BY_NAME['purchase.order']
    assert issubclass(order, BaseModel)
    assert order._description == 'Purchase Order'
    assert order._rec_names_search == ['name', 'partner_ref']
    assert order._order == 'priority desc, id desc'


def test_the_order_inherits_the_five_source_mixins():
    """≙ ``_inherit = ['portal.mixin', 'product.catalog.mixin',
    'mail.thread', 'mail.activity.mixin', 'account.document.import.mixin']``
    (:23)."""
    order = MODELS_BY_NAME['purchase.order']
    for mixin in (PortalMixin, ProductCatalogMixin, MailThread,
                  MailActivityMixin, AccountDocumentImportMixin):
        assert issubclass(order, mixin), mixin.__name__


def test_the_line_inherits_the_analytic_mixin():
    """≙ ``_inherit = ['analytic.mixin']`` (purchase_order_line.py:15)."""
    assert issubclass(MODELS_BY_NAME['purchase.order.line'], AnalyticMixin)


def test_the_line_is_registered_under_its_source_name():
    line = MODELS_BY_NAME['purchase.order.line']
    assert issubclass(line, BaseModel)
    assert line._description == 'Purchase Order Line'
    assert line._order == 'order_id, sequence, id'


def test_priority_and_partner_ref_follow_the_source():
    """≙ ``priority`` (:78-79) y ``partner_ref`` (:83-87)."""
    order = MODELS_BY_NAME['purchase.order']
    priority = order._meta.get_field('priority')
    assert priority.default == '0'
    assert [key for key, _ in priority.choices] == ['0', '1']
    assert priority.db_index
    assert order._meta.get_field('partner_ref').get_internal_type() in (
        'CharField', 'TextField')


def test_the_line_has_its_sequence():
    """≙ ``sequence = fields.Integer(default=10)`` (:22)."""
    line = MODELS_BY_NAME['purchase.order.line']
    assert line._meta.get_field('sequence').default == 10


def test_orders_sort_by_priority_then_newest(db):
    order = MODELS_BY_NAME['purchase.order']
    first = order.objects.create(priority='0')
    urgent = order.objects.create(priority='1')
    last = order.objects.create(priority='0')
    ids = list(order.objects.filter(
        pk__in=[first.pk, urgent.pk, last.pk]).values_list('pk', flat=True))
    assert ids == [urgent.pk, last.pk, first.pk]
