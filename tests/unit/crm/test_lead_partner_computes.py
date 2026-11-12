"""Los cálculos de una iniciativa que derivan del cliente, en alta y después.

≙ ``odoo19c: addons/crm/models/crm_lead.py:402-519``: ``_compute_name``,
``_compute_function``, ``_compute_website``, ``_compute_email_from``
(``partner_id.email``) y ``_compute_phone`` (``partner_id.phone``). Los
cinco son almacenados y editables: en alta se calculan sólo si el valor no
se dio (``fname not in vals``), y un cambio del cliente los recalcula.
Matriz: outputs/stored-compute-field-matrix.tsv (huecos de ``crm.CrmLead``).
"""
import pytest

from addons.base.models import ResPartner
from addons.crm.models import CrmLead
from orm.environments import env as current_env
from orm.environments import transaction_scope

pytestmark = pytest.mark.django_db


def _flush():
    with transaction_scope():
        current_env().flush_all()


@pytest.fixture
def partner():
    return ResPartner.objects.create(
        name='Ana Ruiz', function='CTO', website='https://acme.example',
        email='ana@acme.example', phone='+525512345678')


def _row(lead):
    return CrmLead.objects.values(
        'name', 'function', 'website', 'email_from', 'phone').get(pk=lead.pk)


def test_a_lead_takes_its_partner_values_on_creation(partner):
    lead = CrmLead.objects.create(partner_id=partner)
    _flush()
    assert _row(lead) == {
        'name': "Ana Ruiz's opportunity", 'function': 'CTO',
        'website': 'https://acme.example', 'email_from': 'ana@acme.example',
        'phone': '+525512345678'}


def test_a_given_value_is_kept_on_creation(partner):
    lead = CrmLead.objects.create(partner_id=partner, name='Renovación',
                                  function='Compras')
    _flush()
    row = _row(lead)
    assert row['name'] == 'Renovación'
    assert row['function'] == 'Compras'


def test_a_new_partner_email_reaches_the_lead(partner):
    lead = CrmLead.objects.create(partner_id=partner)
    _flush()
    partner.email = 'ana.ruiz@acme.example'
    partner.save(update_fields=['email'])
    _flush()
    assert _row(lead)['email_from'] == 'ana.ruiz@acme.example'
