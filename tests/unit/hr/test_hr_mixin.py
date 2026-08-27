"""``hr.mixin`` — mixin abstracto (addon ``hr``).

Adaptación fiel de Odoo hr/models/hr_mixin.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3).

``create``/``write`` quedan BLOQUEADOS en este tramo (ver el docstring del
módulo) — sin ``hr.employee`` no hay mecanismo que probar con
comportamiento observable. Esta prueba cubre lo único portado: la cabecera
de clase y su naturaleza abstracta (sin tabla propia).
"""
import pytest

from addons.hr.models import HrMixin

pytestmark = pytest.mark.django_db


class TestHrMixinHeader:

    def test_is_abstract_with_no_own_table(self):
        assert HrMixin._meta.abstract is True

    def test_name_and_description_match_the_reference(self):
        assert HrMixin._name == 'hr.mixin'
        assert HrMixin._description == 'hr.mixin'
