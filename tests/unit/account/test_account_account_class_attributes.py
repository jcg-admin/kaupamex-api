"""La cabecera de ``account.account`` frente a la fuente.

≙ ``AccountAccount`` (``odoo19c: addons/account/models/account_account.py:
19-25``). Con ``_name`` el modelo entra en ``MODELS_BY_NAME`` y
``env['account.account']`` resuelve, que es el respaldo de ``account_id`` en
la envoltura de base-lines.
"""

import pytest

from addons.account.models import AccountAccount
from orm import models
from orm.environments import Environment
from orm.utils import SUPERUSER_ID

pytestmark = pytest.mark.unit


def test_the_class_attributes_the_source_declares():
    assert AccountAccount._name == 'account.account'
    assert AccountAccount._inherit == ['mail.thread', 'mail.activity.mixin']
    assert AccountAccount._description == 'Account'
    assert AccountAccount._order == 'code, placeholder_code'
    assert AccountAccount._check_company_auto is True


def test_the_company_domain_stays_on_the_single_company_field():
    """Divergencia declarada: la fuente usa
    ``check_companies_domain_parent_of``
    sobre el M2M ``company_ids``, que aquí no existe; con él este modelo
    dejaría de participar en la comprobación de empresa. El singular conserva
    el criterio jerárquico sobre ``company``."""
    assert (AccountAccount._check_company_domain.__func__
            is models.check_company_domain_parent_of)
    assert models.check_companies_domain_parent_of(AccountAccount, []) is None


@pytest.mark.django_db
def test_the_environment_resolves_the_model_by_its_name():
    with Environment(None, SUPERUSER_ID, {}) as env:
        assert env['account.account'] is AccountAccount
