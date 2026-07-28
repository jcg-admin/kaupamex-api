"""
Tests — Metodos de envio admin (UC-CFG-02).

CRUD sobre /api/v2/admin/shipping-methods/ — ShippingMethodViewSet
(apps/settings_app/views.py). Cubre: exito (crear/listar/editar/soft-delete),
permisos (anon 401, comprador 403) y validacion de error con ``codigo_error``
(soft-delete bloqueado por ordenes activas).
"""
import pytest
from decimal import Decimal

from addons.orders.models import Order
from addons.delivery.models import ShippingMethod
from addons.sale.models import SaleOrder
from addons.payment.models import Payment
from tests.factories.order_factory import make_order

pytestmark = pytest.mark.integration

LIST_URL   = '/api/v2/admin/shipping-methods/'
DETAIL_URL = lambda pk: f'/api/v2/admin/shipping-methods/{pk}/'


@pytest.fixture
def shipping_method(db):
    return ShippingMethod.objects.create(
        name='Estandar', cost=Decimal('99.00'), estimated_days=5,
        is_active=True,
    )


class TestShippingMethods:

    # --- permisos ---
    def test_anon_recibe_401(self, api_client, db):
        r = api_client.get(LIST_URL)
        assert r.status_code == 401

    def test_comprador_recibe_403(self, auth_client, db):
        r = auth_client.get(LIST_URL)
        assert r.status_code == 403

    # --- exito ---
    def test_admin_crea_metodo(self, admin_client, db):
        r = admin_client.post(LIST_URL, {
            'name': 'Express',
            'cost': '199.00',
            'estimated_days': 2,
        }, format='json')
        assert r.status_code == 201
        body = r.json()
        assert body['name'] == 'Express'
        assert Decimal(str(body['cost'])) == Decimal('199.00')
        assert body['is_active'] is True

    def test_admin_lista_metodos(self, admin_client, shipping_method):
        r = admin_client.get(LIST_URL)
        assert r.status_code == 200
        # Paginado o lista plana — normalizar.
        body = r.json()
        rows = body['results'] if isinstance(body, dict) and 'results' in body else body
        assert any(row['name'] == 'Estandar' for row in rows)

    def test_admin_edita_metodo(self, admin_client, shipping_method):
        r = admin_client.patch(
            DETAIL_URL(shipping_method.pk),
            {'cost': '120.50'},
            format='json',
        )
        assert r.status_code == 200
        assert Decimal(str(r.json()['cost'])) == Decimal('120.50')

    def test_admin_desactiva_metodo_soft_delete(self, admin_client, shipping_method):
        r = admin_client.delete(DETAIL_URL(shipping_method.pk))
        assert r.status_code == 204
        shipping_method.refresh_from_db()
        # Soft delete: la fila persiste con is_active=False.
        assert shipping_method.is_active is False

    # --- validacion / errores ---
    def test_costo_negativo_400(self, admin_client, db):
        r = admin_client.post(LIST_URL, {
            'name': 'Mal', 'cost': '-5.00', 'estimated_days': 3,
        }, format='json')
        assert r.status_code == 400

    def test_dias_estimados_invalidos_400(self, admin_client, db):
        r = admin_client.post(LIST_URL, {
            'name': 'Mal2', 'cost': '10.00', 'estimated_days': 0,
        }, format='json')
        assert r.status_code == 400

    def test_desactivar_con_ordenes_activas_loud(self, admin_client, db, user):
        """Soft-delete bloqueado si hay ActiveOrder referenciando el metodo."""
        method = ShippingMethod.objects.create(
            name='Con ordenes', cost=Decimal('50.00'), estimated_days=4,
        )
        # Orden activa que referencia el metodo (estado distinto a terminal).
        make_order(
            user=user, status='PROCESSING', shipping_method=method,
        )
        r = admin_client.delete(DETAIL_URL(method.pk))
        assert r.status_code == 400
        assert r.json()['codigo_error'] == 'METHOD_WITH_ACTIVE_ORDERS'
        method.refresh_from_db()
        assert method.is_active is True

    def test_desactivar_con_orden_pagada_sin_guia_loud(self, admin_client, db, user):
        """H-API-14: una venta PAID canónica (pagada, aún sin guía) protege su
        método de envío. Antes quedaba fuera de ``ActiveOrder`` y el método se
        podía desactivar dejando la orden pagada sin transporte."""
        method = ShippingMethod.objects.create(
            name='Con orden pagada', cost=Decimal('50.00'), estimated_days=4,
        )
        so = SaleOrder.objects.create(state=SaleOrder.STATE_SALE)
        order = Order.objects.create(
            user=user, sale_order=so, shipping_method=method,
        )
        Payment.objects.create(
            order=order, sale_order=so,
            gateway=Payment.GATEWAY_MERCADOPAGO,
            amount=Decimal('100.00'), status=Payment.STATUS_APPROVED,
        )
        r = admin_client.delete(DETAIL_URL(method.pk))
        assert r.status_code == 400
        assert r.json()['codigo_error'] == 'METHOD_WITH_ACTIVE_ORDERS'
        method.refresh_from_db()
        assert method.is_active is True
