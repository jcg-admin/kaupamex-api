"""``account.code.mapping`` (tarea #398, tramo 2) y su premisa.

``account_code_mapping.py`` declaraba la divergencia porque la premisa de la
referencia —una cuenta compartida entre compañías, con un código distinto
por compañía— no existía aquí. Desde MC2c-1 existe: la cuenta tiene
``company_ids`` y su código vive por empresa raíz en ``code_store``, sin la
restricción ``(company, code)``. Este archivo fija esa premisa y que el modelo
virtual ya está portado (``designs/account-code-mapping.md``); su conducta la
miden ``test_account_code_mapping_virtual.py``.
"""

import pytest
from django.apps import apps
from django.db.models import ManyToManyField

from addons.account.models.account_account import AccountAccount

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


class TestTheAccountBelongsToManyCompanies:
    def test_the_companies_are_a_manytomany(self):
        field = AccountAccount._meta.get_field('company_ids')
        assert isinstance(field, ManyToManyField)

    def test_there_is_no_unique_company_code_constraint(self):
        """Con varias empresas por cuenta no hay "una" compañía que combinar
        con el código: la unicidad es ``_ensure_code_is_unique``."""
        constraint_names = {c.name for c in AccountAccount._meta.constraints}
        assert 'unique_account_code_company' not in constraint_names


class TestTheVirtualModelIsRegistered:
    def test_registered_under_the_source_name_without_a_table(self):
        """``odoo19c: account_code_mapping.py`` declara ``_auto = False`` y
        ``_table_query = '0'``: el modelo existe y no tiene tabla."""
        model = apps.get_model('account', 'AccountCodeMapping')
        assert model._name == 'account.code.mapping'
        assert model._auto is False
        assert model._meta.managed is False
