"""Lo que ``mail`` cuelga en ``res.company``.

≙ ``odoo19c: addons/mail/models/res_company.py``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
mail-company-extension.md``.
"""
import pytest

from addons.base.models import ResCompany
from addons.mail.models.mail_alias_domain import MailAliasDomain
from tools.mail import formataddr

pytestmark = pytest.mark.django_db


@pytest.fixture
def no_domains():
    """Ninguna empresa con dominio y ningún dominio en la base."""
    ResCompany.objects.update(alias_domain_id=None)
    MailAliasDomain.objects.all().delete()


def test_a_new_company_takes_the_first_domain(no_domains):
    first = MailAliasDomain.objects.create(name='first.example.com')
    MailAliasDomain.objects.create(name='second.example.com', sequence=20)
    company = ResCompany.objects.create(code='acme', name='ACME')
    assert company.alias_domain_id == first


def test_without_domain_the_addresses_are_empty(no_domains):
    company = ResCompany.objects.create(code='acme', name='ACME')
    assert company.alias_domain_id is None
    assert (company.bounce_email, company.bounce_formatted) == ('', '')
    assert (company.catchall_email, company.catchall_formatted) == ('', '')


def test_with_a_domain_the_addresses_come_from_it(no_domains):
    domain = MailAliasDomain.objects.create(name='example.com')
    company = ResCompany.objects.create(code='acme', name='ACME')
    assert company.bounce_email == 'bounce@example.com'
    assert company.bounce_formatted == formataddr(
        ('ACME', 'bounce@example.com'))
    assert company.catchall_email == 'catchall@example.com'
    assert company.catchall_formatted == formataddr(
        ('ACME', 'catchall@example.com'))
    assert company.default_from_email == domain.default_from_email


def test_the_formatted_email_prefers_the_partner(no_domains):
    MailAliasDomain.objects.create(name='example.com')
    company = ResCompany.objects.create(code='acme', name='ACME')
    assert company.email_formatted == company.catchall_formatted
    company.partner.email = 'info@acme.test'
    company.partner.save()
    company.refresh_from_db()
    assert company.email_formatted == company.partner.email_formatted


def test_the_email_colors_have_the_source_defaults(no_domains):
    company = ResCompany.objects.create(code='acme', name='ACME')
    assert company.email_primary_color == '#FFFFFF'
    assert company.email_secondary_color == '#875A7B'
