"""``helpdesk.tag`` contra ``odoo19e: helpdesk/models/helpdesk_tag.py``.

Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
basemodel-adoption-helpdesk.md``, unidad 1.
"""
import pytest
from django.db import IntegrityError, transaction

from addons.helpdesk.models import HelpdeskTag
from orm.environments import sudo
from orm.models import BaseModel

pytestmark = pytest.mark.django_db


def test_the_tag_is_a_base_model_with_the_source_header():
    assert issubclass(HelpdeskTag, BaseModel)
    assert HelpdeskTag._name == 'helpdesk.tag'
    assert HelpdeskTag._description == 'Helpdesk Tags'
    assert HelpdeskTag._order == 'name'
    assert HelpdeskTag._meta.db_table == 'helpdesk_tag'


def test_a_new_tag_gets_a_color_between_1_and_11():
    with sudo():
        tag = HelpdeskTag.create({'name': 'Urgent'})
        assert 1 <= tag.color <= 11


def test_two_tags_cannot_share_a_name():
    with sudo():
        HelpdeskTag.create({'name': 'Billing'})
        with pytest.raises(IntegrityError), transaction.atomic():
            HelpdeskTag.objects.create(name='Billing')


def test_name_create_reuses_a_tag_ignoring_case_and_spaces():
    with sudo():
        tag = HelpdeskTag.create({'name': 'Shipping'})
        assert HelpdeskTag.name_create('  shipping ') == (
            tag.id, tag.display_name)
        assert HelpdeskTag.objects.count() == 1


def test_name_create_creates_a_missing_tag():
    with sudo():
        tag_id, label = HelpdeskTag.name_create('Refund')
    assert HelpdeskTag.objects.get(pk=tag_id).name == 'Refund'
    assert label == 'Refund'
