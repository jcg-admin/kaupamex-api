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


def test_the_company_domain_is_the_plural_on_company_ids():
    """≙ ``_check_company_domain = models.check_companies_domain_parent_of``
    (``odoo19c: addons/account/models/account_account.py:25``): desde MC2c-2
    la cuenta no tiene columna ``company`` y su dominio de empresa es el
    plural sobre ``company_ids``."""
    assert (AccountAccount._check_company_domain.__func__
            is models.check_companies_domain_parent_of)


@pytest.mark.django_db
def test_the_environment_resolves_the_model_by_its_name():
    with Environment(None, SUPERUSER_ID, {}) as env:
        assert isinstance(env['account.account'], AccountAccount)
