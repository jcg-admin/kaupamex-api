"""Shared setter: new Django rows retain notifications without reverse SQL."""
from functools import wraps
from uuid import uuid4

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from addons.base.models import ResBank, ResPartner, ResPartnerBank
from addons.base.models.res_partner import ResPartnerCategory
from addons.sale.models import SaleOrder
from addons.sale_stock.models.sale_order import SaleOrderDelivery
from orm.models import _traverse_inverse


def test_unsaved_partner_item_assignment_keeps_its_value_without_database(django_db_blocker):
    with django_db_blocker.block():
        record = ResPartner(name='Before')
        record['name'] = 'After'
        assert record.name == 'After'
        assert record.pk is None


def test_unsaved_reverse_many_to_one_has_no_persisted_rows(django_db_blocker):
    with django_db_blocker.block():
        record = ResPartner(name='New parent')
        inverse = ResPartnerBank._meta.get_field('partner').remote_field
        assert _traverse_inverse([record], inverse) == []


def test_unsaved_reverse_many_to_many_does_not_construct_a_database_manager(django_db_blocker):
    with django_db_blocker.block():
        record = ResPartner(name='New categorized parent')
        inverse = ResPartnerCategory._meta.get_field('partners').remote_field
        assert _traverse_inverse([record], inverse) == []


def test_unsaved_forward_many_to_many_has_no_persisted_rows(django_db_blocker):
    with django_db_blocker.block():
        record = ResPartnerCategory(name='New category')
        inverse = ResPartnerCategory._meta.get_field('partners')
        assert _traverse_inverse([record], inverse) == []


def test_cached_new_partner_label_is_invalidated_without_database(django_db_blocker):
    with django_db_blocker.block():
        record = ResPartner(name='Cached before')
        assert record.display_name == 'Cached before'
        record.name = 'Cached after'
        assert record.display_name == 'Cached after'


def test_new_contextual_cache_identity_does_not_invalidate_another_row(
    django_db_blocker, monkeypatch,
):
    calls = []
    original = ResPartner._compute_display_name

    @wraps(original)
    def compute(record):
        calls.append(record.name)
        return original(record)

    monkeypatch.setattr(ResPartner, '_compute_display_name', compute)
    with django_db_blocker.block():
        first = ResPartner(name='First')
        second = ResPartner(name='Second')
        assert first.display_name == 'First'
        assert second.display_name == 'Second'
        assert len(calls) == 2
        first.name = 'First updated'
        assert first.display_name == 'First updated'
        assert second.display_name == 'Second'
        assert len(calls) == 3


def test_cached_new_reverse_one_to_one_remains_traversable(django_db_blocker):
    with django_db_blocker.block():
        order = SaleOrder(name='New order', cart_token=uuid4())
        delivery = SaleOrderDelivery(order=order, incoterm_location='Local only')
        inverse = SaleOrderDelivery._meta.get_field('order').remote_field
        reached = _traverse_inverse([order], inverse)
        assert reached == [delivery]
        assert order.pk is None and delivery.pk is None


@pytest.mark.django_db
def test_saved_reverse_collection_still_reads_actual_rows():
    partner = ResPartner.objects.create(name='Saved parent')
    bank = ResBank.objects.create(name='Saved bank')
    account = ResPartnerBank.objects.create(
        partner=partner, bank=bank, acc_number='01234567891')
    inverse = ResPartnerBank._meta.get_field('partner').remote_field
    with CaptureQueriesContext(connection) as queries:
        reached = _traverse_inverse([partner], inverse)
    assert [row.pk for row in reached] == [account.pk]
    assert len(queries) >= 1


def test_custom_in_memory_collection_is_not_skipped(django_db_blocker, monkeypatch):
    with django_db_blocker.block():
        record = ResPartner(name='Custom collection parent')
        child = ResPartnerBank(partner=record, acc_number='01234567892')
        inverse = ResPartnerBank._meta.get_field('partner').remote_field
        accessor = inverse.get_accessor_name()

        class MemoryManager:
            def all(self):
                return [child]

        class MemoryCollection:
            def __get__(self, instance, owner=None):
                return self if instance is None else MemoryManager()

        monkeypatch.setattr(ResPartner, accessor, MemoryCollection())
        assert _traverse_inverse([record], inverse) == [child]
