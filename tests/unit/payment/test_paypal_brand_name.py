"""
Tests — nombre público de checkout de PayPal (H-API-395).

``brand_name`` del payload de PayPal debe reflejar el nombre de la Company
(L1) dueña de la orden, NO un valor fijo — antes hardcodeaba 'Kaupamex'
(el operador L0) para toda orden, colapsando L0/L1 en el checkout que ve
el comprador.

Cubre ``addons.payment_paypal.gateway._resolve_brand_name``, la función
pura (sin red) que ``create_preference`` usa para ``brand_name`` y para la
``description`` de cada ``purchase_unit``.
"""
import pytest

from addons.base.models import ResCompany
from addons.payment_paypal.gateway import (
    PAYPAL_BRAND_NAME_DEFAULT,
    _resolve_brand_name,
)
from addons.sale.status_projection import STATUS_PENDING
from tests.factories.order_factory import make_order

pytestmark = pytest.mark.unit


class TestResolveBrandName:

    def test_reflects_the_owning_company_name(self, db):
        acme = ResCompany.objects.create(code='acme-paypal-brand', name='Acme Corp')
        order = make_order(status=STATUS_PENDING, company=acme)

        assert _resolve_brand_name(order) == 'Acme Corp'
        assert _resolve_brand_name(order) != PAYPAL_BRAND_NAME_DEFAULT

    def test_falls_back_to_neutral_platform_default_without_company(self, db):
        order = make_order(status=STATUS_PENDING, company=None)

        assert _resolve_brand_name(order) == PAYPAL_BRAND_NAME_DEFAULT
        assert PAYPAL_BRAND_NAME_DEFAULT == 'Kaupamex'
