"""Fechas y ingresos recurrentes de una iniciativa, en alta y después.

≙ ``odoo19c: addons/crm/models/crm_lead.py:359-390`` y ``:573-586``.
``_compute_date_open`` y ``_compute_date_last_stage_update`` fechan con
``self.env.cr.now()``, la hora de la transacción: la misma que pone
``create_date`` en el alta, así que ``day_open`` sale 0. Los ingresos
recurrentes dependen de ``recurring_plan.number_of_months``, un campo de
otro modelo.
"""
from decimal import Decimal

import pytest

from addons.base.models import ResPartner, ResUsers
from addons.crm.models import CrmLead
from addons.crm.models.crm_recurring_plan import CrmRecurringPlan
from orm.environments import env as current_env
from orm.environments import transaction_scope

pytestmark = pytest.mark.django_db


def _flush():
    with transaction_scope():
        current_env().flush_all()


@pytest.fixture
def salesman():
    partner = ResPartner.objects.create(name='Vendedora')
    return ResUsers.objects.create(login='vendedora.crm', partner=partner)


def test_the_open_and_stage_dates_are_the_transaction_time(salesman):
    lead = CrmLead.objects.create(name='Iniciativa', user_id=salesman)
    _flush()
    row = CrmLead.objects.values(
        'create_date', 'date_open', 'date_last_stage_update',
        'day_open').get(pk=lead.pk)
    assert row['date_open'] == row['create_date']
    assert row['date_last_stage_update'] == row['create_date']
    assert row['day_open'] == 0


def test_the_recurring_revenues_follow_the_plan():
    plan = CrmRecurringPlan.objects.create(name='Anual', number_of_months=12)
    lead = CrmLead.objects.create(
        name='Suscripción', recurring_plan=plan,
        recurring_revenue=Decimal('1200'), probability=50)
    _flush()
    columns = ('recurring_revenue_monthly',
               'recurring_revenue_monthly_prorated',
               'recurring_revenue_prorated')
    row = CrmLead.objects.values(*columns).get(pk=lead.pk)
    assert [float(row[c]) for c in columns] == [100.0, 50.0, 600.0]

    plan.number_of_months = 6
    plan.save(update_fields=['number_of_months'])
    _flush()
    row = CrmLead.objects.values(*columns).get(pk=lead.pk)
    assert [float(row[c]) for c in columns] == [200.0, 100.0, 600.0]
