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


ENGLISH_CATEGORIES = {'sales', 'operations', 'finance', 'marketing', 'support', 'platform'}


def test_sellable_modules_are_applications():
    _seed()
    for code in ('catalogue', 'orders', 'payments', 'invoices', 'inventory',
                 'logistics', 'finance', 'reports', 'newsletter', 'support'):
        m = Module.objects.get(code=code)
        assert m.is_application is True, code
        assert m.category in ENGLISH_CATEGORIES, (code, m.category)


def test_all_categories_are_english_identifiers():
    """Los identificadores de categoría son inglés (canon DEC-DOC-005)."""
    _seed()
    used = set(
        Module.objects.exclude(category='').values_list('category', flat=True)
    )
    assert used <= ENGLISH_CATEGORIES, used


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
