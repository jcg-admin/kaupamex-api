"""Tests — I1: la identidad pública del contrato migra a ``sale.name``.

Decisión del ejecutor (2026-07-28, H-API-29): el contrato público migra a
``sale.name``, coordinando con la UI. La implementación de mínima fricción
es por el **valor**, no por el nombre del campo: el puente crea el espejo
con ``order_number = sale.name`` (``S-…``), de modo que los ~197 sitios de
producción que emiten ``order_number`` publican la identidad canónica sin
tocarse, los lookups por ``order_number`` resuelven igual (ambas columnas
UNIQUE), y la UI —que trata el valor como opaco (los ``PY-`` sólo viven en
mocks)— no requiere cambio de contrato.

Órdenes previas conservan su ``PY-…`` (entorno dev, datos desechables —
autorización del ejecutor; sin data migration de ids).
"""
import re
from decimal import Decimal
from uuid import uuid4

import pytest

from addons.catalogue.models import Category, Product
from addons.orders.models import Order
from addons.sale.models import SaleOrder, SaleOrderLine
from addons.sale.services import add_item_to_draft, confirm_draft_order

pytestmark = pytest.mark.django_db

ADDR = {
    'recipient_name': 'Identidad I1', 'street': 'Calle 1', 'city': 'CDMX',
    'state': 'CDMX', 'zip_code': '01000',
}


@pytest.fixture
def producto():
    cat = Category.objects.create(name='Cat I1', slug='cat-i1', is_active=True)
    prod = Product.objects.create(
        name='Prod I1', slug='prod-i1', sku='SKU-I1',
        price=Decimal('80.00'), stock=5, is_active=True, is_published=True)
    prod.categories.add(cat)
    return prod


def _confirmar(producto):
    draft = SaleOrder.objects.create(
        state=SaleOrder.STATE_DRAFT, cart_token=uuid4())
    add_item_to_draft(draft, producto, quantity=1)
    legacy = confirm_draft_order(draft, address_data=dict(ADDR),
                                 guest_email='i1@test.mx')
    draft.refresh_from_db()
    return draft, legacy


class TestIdentidadCanonicaEnElContrato:

    def test_el_espejo_nace_con_la_identidad_canonica(self, producto):
        canonical, legacy = _confirmar(producto)
        assert legacy.order_number == canonical.name
        # Formato Odoo seq_sale_order: prefix 'S' + padding 5 (S00001…).
        assert re.match(r'^S\d{5,}$', legacy.order_number)

    def test_lookup_publico_por_order_number_resuelve_la_venta(self, producto):
        """El patrón de lookup vigente (``order_number``) sigue resolviendo,
        y ahora es equivalente a buscar por ``sale.name``."""
        canonical, legacy = _confirmar(producto)
        assert Order.objects.get(order_number=canonical.name).pk == legacy.pk
        assert SaleOrder.objects.get(name=legacy.order_number).pk == canonical.pk
