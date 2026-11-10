"""Las dos rutas de dominio que faltaban a las reglas de ``hr``.

≙ ``odoo19c: addons/hr/security/hr_security.xml``::

    ir_rule_res_partner_bank_internal_users  (:64-66)
        [('partner_id.employee_ids', '=', False)]
    ir_rule_hr_departure_reason_multi_company (:100-101)
        [('country_code', 'in', user.env.companies.mapped('country_code')
          + [False])]

``employee_ids`` es el One2many de ``hr/models/res_partner.py:11-13``
(inverso de ``work_contact_id``) y ``country_code`` el relacionado no
almacenado de ``hr/models/hr_departure_reason.py:15``. Diseño:
``designs/module-install-cycle.md``, L4b.
"""
import pytest

from addons.base.models import (
    ResBank, ResCountry, ResPartner, ResPartnerBank,
)
from addons.hr.models import HrDepartureReason, HrEmployee
from orm.domains import to_q
from orm.environments import sudo
from orm.utils import model_field_registry

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _as_superuser(db):
    """Miden la ruta del dominio, no el acceso: eso es la unidad L5."""
    with sudo():
        yield


@pytest.fixture
def mexico():
    return ResCountry.objects.get(code='MX')


def _matching(model, domain):
    """Las filas que el dominio admite, compilado como lo compila
    ``ir.rule`` (``ir_rule.py``: ``queryset.filter(domain._to_q(model))``)."""
    return sorted(model.objects.filter(to_q(domain, model))
                  .values_list('pk', flat=True))


def _account(partner, number, country):
    bank = ResBank.objects.create(
        name='Banco %s' % number, bic='RULE%sMM' % number[-2:],
        country=country,
    )
    return ResPartnerBank.objects.create(
        acc_number=number, bank=bank, partner=partner,
    )


def test_the_partner_has_the_employee_ids_of_the_source():
    field = model_field_registry(ResPartner)['employee_ids']
    assert field.related_model is HrEmployee
    assert field.remote_field.name == 'work_contact'


def test_the_bank_rule_path_separates_the_employee_accounts(mexico):
    work_contact = ResPartner.objects.create(name='Contacto del empleado')
    HrEmployee.objects.create(name='Con cuenta', work_contact=work_contact)
    contact = ResPartner.objects.create(name='Contacto externo')
    employee_account = _account(work_contact, '0111222333441', mexico)
    other_account = _account(contact, '0111222333442', mexico)
    assert _matching(ResPartnerBank, [
        ('id', 'in', [employee_account.pk, other_account.pk]),
        ('partner_id.employee_ids', '=', False),
    ]) == [other_account.pk]


def test_the_reason_has_country_code_as_a_field():
    assert 'country_code' in model_field_registry(HrDepartureReason)


def test_the_reason_rule_path_filters_by_country_code(mexico):
    other = ResCountry.objects.exclude(code='MX').first()
    in_mexico = HrDepartureReason.objects.create(
        name='En México', country=mexico)
    elsewhere = HrDepartureReason.objects.create(
        name='En otro país', country=other)
    without = HrDepartureReason.objects.create(name='Sin país', country=None)
    assert _matching(HrDepartureReason, [
        ('id', 'in', [in_mexico.pk, elsewhere.pk, without.pk]),
        ('country_code', 'in', ['MX', False]),
    ]) == sorted([in_mexico.pk, without.pk])
    assert in_mexico.country_code == 'MX'
