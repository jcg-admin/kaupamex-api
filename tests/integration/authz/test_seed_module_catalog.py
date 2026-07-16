"""``seed_authz`` clasifica NUESTROS módulos en el catálogo L0 (#179).

Tras el seed, cada ``Module`` de Kaupamex lleva su metadata de catálogo:
``is_application`` (app vendible vs técnico) + ``category``. El ``tier`` queda
en el default ``free`` — el pricing (free/paid por módulo) es GAP 4 / #180 y no
se fija aquí (no inventar precios). Idempotente: re-ejecutar no cambia nada.
"""
import pytest
from django.core.management import call_command

from apps.platform.authz.models import Module

pytestmark = pytest.mark.django_db


def _seed():
    call_command('seed_authz')


# Familias funcionales ERP (taxonomía NetSuite/Odoo manifest ``category``),
# no etiquetas planas: Order Management ≠ SCM ≠ Finance ≠ CRM ≠ Employee
# Management. Employee Management (HR/HCM) es familia futura — ningún módulo
# actual la ocupa, pero es canónica. Valor = display string en inglés.
ERP_FAMILIES = {
    'Order Management', 'Supply Chain Management', 'Finance', 'CRM',
    'Employee Management', 'Platform',
}


def test_sellable_modules_are_applications():
    _seed()
    for code in ('catalogue', 'orders', 'payments', 'invoices', 'inventory',
                 'logistics', 'finance', 'reports', 'newsletter', 'support'):
        m = Module.objects.get(code=code)
        assert m.is_application is True, code
        assert m.category in ERP_FAMILIES, (code, m.category)


def test_billing_pieces_are_order_management_not_finance():
    """Facturación/invoices son Order Management, no Finance (PROVEN en
    ``analisis-ubicacion-modulo-billing-order-management``: el continuo
    comercial Sales Order → Fulfill → Invoice → Payment → Returns)."""
    _seed()
    for code in ('orders', 'payments', 'invoices', 'returns', 'logistics'):
        assert Module.objects.get(code=code).category == 'Order Management', code


def test_all_categories_are_canonical_erp_families():
    """Toda categoría usada es una familia funcional ERP canónica (inglés)."""
    _seed()
    used = set(
        Module.objects.exclude(category='').values_list('category', flat=True)
    )
    assert used <= ERP_FAMILIES, used


def test_technical_modules_are_not_applications():
    _seed()
    for code in ('audit', 'backups', 'permissions', 'platform', 'settings',
                 'users', 'account', 'notifications'):
        m = Module.objects.get(code=code)
        assert m.is_application is False, code


def test_tier_stays_free_pricing_deferred():
    """Ningún módulo se marca paid en el seed (pricing = GAP 4 / #180)."""
    _seed()
    assert not Module.objects.filter(tier=Module.Tier.PAID).exists()


def test_seed_is_idempotent_for_catalog():
    _seed()
    apps_first = set(
        Module.objects.filter(is_application=True).values_list('code', flat=True)
    )
    _seed()
    apps_second = set(
        Module.objects.filter(is_application=True).values_list('code', flat=True)
    )
    assert apps_first == apps_second
