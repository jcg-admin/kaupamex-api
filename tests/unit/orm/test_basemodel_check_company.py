"""``BaseModel`` trae ``_check_company``, como en la fuente.

≙ ``odoo19c: odoo/orm/models.py:4009-4012``: ``_check_company`` es un método
de ``BaseModel``, y ``create``/``write`` lo invocan cuando
``_check_company_auto`` es verdadero. Un modelo que declara el atributo sin
heredar el método revienta al escribir por el ORM.
"""
import pytest
from django.apps import apps

from addons.account.models import AccountReconcileModel
from addons.base.models import ResCompany, ResPartner
from orm.commands import Command
from orm.models import BaseModel


def test_every_basemodel_that_checks_the_company_can_check_it():
    missing = [
        model.__name__
        for model in apps.get_models()
        if issubclass(model, BaseModel)
        and getattr(model, '_check_company_auto', False)
        and not hasattr(model, '_check_company')
    ]
    assert missing == []


def test_basemodel_carries_the_company_check():
    assert any('_check_company' in klass.__dict__
               for klass in BaseModel.__mro__)


@pytest.mark.django_db
def test_a_reconcile_rule_writes_through_the_orm():
    company = ResCompany.objects.create(
        name='Kaupamex', code='kaupamex_test_check_company')
    rule = AccountReconcileModel.objects.create(
        name='Comisiones', company=company)
    partner = ResPartner.objects.create(name='Banco')
    rule.sudo().write({'match_partner_ids': [Command.link(partner.pk)]})
    assert list(rule.match_partner_ids) == [partner]
