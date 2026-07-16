"""Catálogo L0 — metadata de ``Module`` (diseno-catalogo-l0-module-extendido).

Verifica los campos de catálogo que extienden ``Module`` con el contrato del
``__manifest__`` de Odoo (is_application / tier / category / version /
description / auto_install). El tier de pago vive en la metadata del módulo,
no en la carpeta (principio PROVEN por Odoo). Enums en inglés (free/paid).
"""
import pytest

from apps.platform.authz.models import Module


@pytest.mark.django_db
class TestModuleCatalogFields:
    def test_defaults_are_technical_free(self):
        """Un módulo nuevo es técnico (no vendible) y gratis por defecto."""
        m = Module.objects.create(code='catalog-x', name='Catalog X')
        m.refresh_from_db()
        assert m.is_application is False
        assert m.tier == Module.Tier.FREE
        assert m.category == ''
        assert m.version == ''
        assert m.description == ''
        assert m.auto_install is False

    def test_can_mark_application_paid_with_metadata(self):
        """Una app vendible de pago lleva su metadata de catálogo."""
        m = Module.objects.create(
            code='crm', name='CRM', is_application=True,
            tier=Module.Tier.PAID, category='sales', version='1.0.0',
            description='Customer relationship management', auto_install=False,
        )
        m.refresh_from_db()
        assert m.is_application is True
        assert m.tier == Module.Tier.PAID
        assert m.get_tier_display() == 'De pago'
        assert m.category == 'sales'
        assert m.version == '1.0.0'
        assert m.description == 'Customer relationship management'

    def test_tier_choices_are_english_values(self):
        """Los valores del enum son inglés (free/paid), etiquetas en español."""
        assert [c[0] for c in Module.Tier.choices] == ['free', 'paid']

    def test_auto_install_technical_module(self):
        """Un módulo técnico puede marcarse auto_install (se activa con deps)."""
        m = Module.objects.create(
            code='core-bridge', name='Core Bridge', auto_install=True,
        )
        m.refresh_from_db()
        assert m.auto_install is True
        assert m.is_application is False
