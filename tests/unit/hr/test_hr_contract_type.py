"""``hr.contract.type`` — catálogo de tipos de contrato (addon ``hr``).

Adaptación fiel de Odoo hr/models/hr_contract_type.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3).
"""
import pytest

from addons.hr.models import HrContractType

pytestmark = pytest.mark.django_db


class TestHrContractTypeCode:
    """``save()`` auto-rellena ``code`` — ≙ ``_compute_code``."""

    def test_save_fills_code_from_name_when_empty(self):
        contract_type = HrContractType.objects.create(name='Indefinido')
        assert contract_type.code == 'Indefinido'

    def test_save_preserves_an_explicit_code(self):
        contract_type = HrContractType.objects.create(
            name='Indefinido', code='CDI')
        assert contract_type.code == 'CDI'

    def test_code_is_not_overwritten_on_subsequent_saves(self):
        contract_type = HrContractType.objects.create(name='Temporal')
        contract_type.code = 'TEMP'
        contract_type.save()
        contract_type.refresh_from_db()
        assert contract_type.code == 'TEMP'


class TestHrContractTypeOrdering:

    def test_default_ordering_is_by_sequence(self):
        HrContractType.objects.create(name='Segundo', sequence=20)
        HrContractType.objects.create(name='Primero', sequence=10)
        names = list(
            HrContractType.objects.order_by(
                *HrContractType._meta.ordering).values_list('name', flat=True))
        assert names == ['Primero', 'Segundo']


class TestHrContractTypeStr:

    def test_str_returns_name(self):
        contract_type = HrContractType.objects.create(name='Indefinido')
        assert str(contract_type) == 'Indefinido'
