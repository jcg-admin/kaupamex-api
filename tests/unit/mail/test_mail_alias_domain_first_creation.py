"""El arranque del primer dominio de alias.

≙ ``odoo19c: addons/mail/models/mail_alias_domain.py:152-163``: al crear el
primer dominio, se asigna a toda empresa —archivada o no— y a todo alias que
aún no tengan dominio. Un dominio posterior no los toca.
"""
import pytest

from addons.base.models.ir_model import IrModel
from addons.base.models.res_company import ResCompany
from addons.mail.models.mail_alias import MailAlias
from addons.mail.models.mail_alias_domain import MailAliasDomain

pytestmark = pytest.mark.django_db


@pytest.fixture
def no_domains():
    MailAlias.objects.update(alias_domain=None)
    ResCompany.objects.update(alias_domain_id=None)
    MailAliasDomain.objects.all().delete()


def test_the_first_domain_reaches_every_company(no_domains):
    archived = ResCompany.objects.create(name='Archivada', active=False)
    domain = MailAliasDomain.objects.create(name='primero.mx')
    assert ResCompany.objects.filter(alias_domain_id__isnull=True).count() == 0
    archived.refresh_from_db()
    assert archived.alias_domain_id == domain


def test_the_first_domain_reaches_every_alias(no_domains):
    alias = MailAlias.objects.create(
        alias_name='ventas',
        alias_model=IrModel.objects.create(model='orders.Order',
                                           name='orders.Order'))
    domain = MailAliasDomain.objects.create(name='primero.mx')
    alias.refresh_from_db()
    assert alias.alias_domain_id == domain.pk
    assert alias.alias_full_name == 'ventas@primero.mx'


def test_a_later_domain_leaves_them_alone(no_domains):
    earlier = ResCompany.objects.create(name='Anterior')
    first = MailAliasDomain.objects.create(name='primero.mx')
    company = ResCompany.objects.create(name='Nueva')
    company.alias_domain_id = None
    company.save()
    MailAliasDomain.objects.create(name='segundo.mx')
    company.refresh_from_db()
    earlier.refresh_from_db()
    assert company.alias_domain_id is None
    assert earlier.alias_domain_id == first
