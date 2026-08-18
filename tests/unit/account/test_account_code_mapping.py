"""``account.code.mapping`` (tarea #398, tramo 2) — divergencia de mecanismo.

No hay modelo Django que probar: ``account_code_mapping.py`` declara por qué
la premisa de la referencia (una cuenta compartida entre compañías, con un
código distinto por compañía) no existe en este árbol —
``AccountAccount.company`` es un ``ForeignKey`` 1:1, no un ``ManyToMany``. Lo
que este test fija es exactamente esa premisa, para que la divergencia deje
de ser válida el día que alguien la cambie sin darse cuenta.
"""
import pytest
from django.apps import apps
from django.db.models import ForeignKey, ManyToManyField

from addons.account.models.account_account import AccountAccount

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


class TestTheAccountAccountCompanyPremiseIsStillOneToOne:
    def test_company_is_a_foreignkey_not_a_manytomany(self):
        field = AccountAccount._meta.get_field('company')
        assert isinstance(field, ForeignKey)
        assert not isinstance(field, ManyToManyField)

    def test_there_is_a_unique_company_code_constraint(self):
        """La UNIQUE(company, code) sólo tiene sentido en el modelo 1:1 —
        si ``company`` fuera M2M, esta restricción no podría existir tal cual
        (una fila no tiene "una" compañía que combinar con el código)."""
        constraint_names = {c.name for c in AccountAccount._meta.constraints}
        assert 'unique_account_code_company' in constraint_names


class TestNoAccountCodeMappingModelExists:
    def test_no_app_registers_that_model_label(self):
        """``account.code.mapping`` no aparece en ninguna app instalada — se
        declaró la divergencia, no se fabricó el modelo virtual."""
        model_labels = {
            model._meta.model_name for model in apps.get_models()
        }
        assert 'accountcodemapping' not in model_labels
