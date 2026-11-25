"""``account.code.mapping`` (tarea #398, tramo 2) — divergencia de mecanismo.

``account_code_mapping.py`` declaraba la divergencia porque la premisa de la
referencia —una cuenta compartida entre compañías, con un código distinto
por compañía— no existía aquí. Desde MC2c-1 existe: la cuenta tiene
``company_ids`` y su código vive por empresa raíz en ``code_store``, sin la
restricción ``(company, code)``. Este test fija la premisa nueva; el modelo
virtual pasa a ser un sucesor (``designs/account-account-mc2c.md``).
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


class TestNoAccountCodeMappingModelExists:
    def test_no_app_registers_that_model_label(self):
        """``account.code.mapping`` no aparece en ninguna app instalada — se
        declaró la divergencia, no se fabricó el modelo virtual."""
        model_labels = {model._meta.model_name for model in apps.get_models()}
        assert 'accountcodemapping' not in model_labels
