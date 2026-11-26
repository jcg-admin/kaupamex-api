"""``report.layout`` sobre ``models.BaseModel``.

≙ ``odoo19c: odoo/addons/base/models/report_layout.py:7-17`` y
``odoo/addons/base/security/ir.model.access.csv:123``. Diseño:
``designs/basemodel-adoption-report-layout.md``.
"""

import pytest
from django.db import IntegrityError, transaction

from addons.base.models import IrModelData, ResGroups, ResPartner, ResUsers
from addons.base.models.ir_ui_view import IrUiView
from addons.base.models.report_layout import ReportLayout
from exceptions import AccessError
from orm.environments import Environment, sudo, user_scope

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def _view(key):
    return IrUiView.objects.create(
        name=key, key=key, type='qweb', arch_db='<t t-name="x"/>')


def _user(login, xmlid):
    with sudo():
        partner = ResPartner.objects.create(name=login, email='')
        user = ResUsers.objects.create(login=login, partner=partner)
        user.group_ids.set([ResGroups.objects.get(
            pk=IrModelData._xmlid_to_res_id(xmlid, raise_if_not_found=True))])
    return user


def test_an_internal_user_creates_and_reads_layouts():
    """ACL de ``group_user`` (``ir.model.access.csv:123``)."""
    user = _user('layout-internal@kaupamex.test', 'base.group_user')
    view = _view('layout.internal')
    with user_scope(user.pk):
        env = Environment(uid=user.pk)['report.layout']
        layout = env.create({'name': 'Light', 'view': view.pk})
        assert env.search([('id', '=', layout.id)]).ids == [layout.id]


def test_a_portal_user_cannot_read_layouts():
    """Sin fila de ACL para el portal."""
    user = _user('layout-portal@kaupamex.test', 'base.group_portal')
    ReportLayout.objects.create(name='Boxed', view=_view('layout.portal'))
    with user_scope(user.pk), pytest.raises(AccessError):
        Environment(uid=user.pk)['report.layout'].search([])


def test_a_layout_needs_a_view():
    """``view_id`` ``required=True`` (``report_layout.py:12``)."""
    with pytest.raises(IntegrityError), transaction.atomic():
        ReportLayout.objects.create(name='Sin vista')
