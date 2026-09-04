"""``hr.employee.category`` — etiqueta de empleado (addon ``hr``).

Adaptación fiel de Odoo hr/models/hr_employee_category.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3).
"""
import pytest
from django.db import IntegrityError, transaction

from addons.hr.models import HrEmployeeCategory

pytestmark = pytest.mark.django_db


class TestHrEmployeeCategoryColor:
    """≙ ``_get_default_color``: ``randint(1, 11)``."""

    def test_default_color_is_within_the_reference_range(self):
        category = HrEmployeeCategory.objects.create(name='Freelance')
        assert 1 <= category.color <= 11

    def test_an_explicit_color_is_respected(self):
        category = HrEmployeeCategory.objects.create(
            name='Directivo', color=4)
        assert category.color == 4


class TestHrEmployeeCategoryUniqueName:
    """≙ ``_name_uniq`` (``models.Constraint('unique (name)', ...)``)."""

    def test_unique_name(self):
        HrEmployeeCategory.objects.create(name='Freelance')
        with transaction.atomic(), pytest.raises(IntegrityError):
            HrEmployeeCategory.objects.create(name='Freelance')


class TestHrEmployeeCategoryStr:

    def test_str_returns_name(self):
        category = HrEmployeeCategory.objects.create(name='Freelance')
        assert str(category) == 'Freelance'
