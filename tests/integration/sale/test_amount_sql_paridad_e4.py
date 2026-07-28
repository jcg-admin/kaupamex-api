"""Tests — E4: paridad entre el importe SQL y el método Python.

Cierra el defecto de agregación de H-API-30. La premisa de toda la rebanada es
que ``AMOUNT_TOTAL_SQL`` da **exactamente** lo mismo que
``SaleOrder.amount_total()``; si divergen aunque sea en un centavo, los
reportes dejarían de cuadrar contra lo que el comprador vio y contra el espejo.

Lo que se fija aquí:

1. Paridad exacta en el caso simple y con las líneas marcadoras de E1-bis
   (envío suma, descuento resta).
2. Paridad bajo redondeo adverso: el método Python cuantiza **por línea**, así
   que la expresión SQL redondea por línea también. Un caso con tres líneas de
   ``33.333`` distingue las dos estrategias.
3. Sin fan-out: ``Count('id')`` junto al ``Sum`` cuenta órdenes, no líneas —
   el defecto clásico de anotar con join sobre una relación a-muchos.
4. Orden sin líneas → ``0.00``, no ``NULL`` (un ``None`` propagaría a los
   payloads de reporte como ausencia de dato, no como cero).
"""
from decimal import Decimal
from uuid import uuid4

import pytest
from django.db.models import Count, Sum

from addons.catalogue.models import Category, Product
from addons.delivery.aggregates import with_delivery_amount
from addons.delivery.models import ShippingMethod
from addons.delivery.models.sale_order import set_delivery_line
from addons.sale.aggregates import with_amounts
from addons.sale.models import SaleOrder, SaleOrderLine
from addons.sale_loyalty.aggregates import with_reward_amount

pytestmark = pytest.mark.django_db


@pytest.fixture
def producto():
    cat = Category.objects.create(name='Cat E4', slug='cat-e4', is_active=True)
    prod = Product.objects.create(
        name='Prod E4', slug='prod-e4', sku='SKU-E4',
        price=Decimal('100.00'), stock=99, is_active=True, is_published=True)
    prod.categories.add(cat)
    return prod


@pytest.fixture
def metodo():
    return ShippingMethod.objects.create(
        name='Estándar E4', cost=Decimal('99.00'), estimated_days=3)


def _orden(producto, **line_kwargs):
    order = SaleOrder.objects.create(
        state=SaleOrder.STATE_DRAFT, cart_token=uuid4())
    defaults = {'product_uom_qty': 1, 'price_unit': Decimal('100.00'),
                'name': 'Prod E4'}
    defaults.update(line_kwargs)
    SaleOrderLine.objects.create(order=order, product=producto, **defaults)
    return order


def _sql_total(order):
    return with_amounts(
        SaleOrder.objects.filter(pk=order.pk)).first().amount_total_sql


class TestParidadConElMetodoPython:

    def test_caso_simple(self, producto):
        order = _orden(producto)
        assert _sql_total(order) == order.amount_total() == Decimal('100.00')

    def test_con_cantidad_y_descuento_de_linea(self, producto):
        order = _orden(producto, product_uom_qty=3, discount=Decimal('10.00'))
        assert _sql_total(order) == order.amount_total() == Decimal('270.00')

    def test_con_linea_de_envio(self, producto, metodo):
        order = _orden(producto)
        order.carrier = metodo
        order.save(update_fields=['carrier', 'updated_at'])
        set_delivery_line(order, Decimal('99.00'))
        assert _sql_total(order) == order.amount_total() == Decimal('199.00')

    def test_con_linea_de_recompensa_negativa(self, producto):
        order = _orden(producto)
        SaleOrderLine.objects.create(
            order=order, product=producto, name='Descuento',
            product_uom_qty=1, price_unit=Decimal('-20.00'), is_reward=True)
        assert _sql_total(order) == order.amount_total() == Decimal('80.00')

    def test_orden_sin_lineas_da_cero_no_null(self):
        order = SaleOrder.objects.create(
            state=SaleOrder.STATE_DRAFT, cart_token=uuid4())
        total = _sql_total(order)
        assert total is not None
        assert total == order.amount_total() == Decimal('0.00')


class TestRedondeoPorLinea:
    """El método Python cuantiza por línea; la expresión SQL debe hacer igual.

    Con tres líneas de ``33.333``: redondear por línea da 33.33×3 = 99.99;
    sumar exacto y redondear al final daría 100.00. Un centavo de diferencia
    por orden es suficiente para descuadrar un reporte de ingresos contra el
    espejo, así que la estrategia no puede quedar implícita.
    """

    def test_cuantiza_por_linea_no_al_final(self, producto):
        order = SaleOrder.objects.create(
            state=SaleOrder.STATE_DRAFT, cart_token=uuid4())
        for _ in range(3):
            SaleOrderLine.objects.create(
                order=order, product=producto, name='Prod E4',
                product_uom_qty=1, price_unit=Decimal('33.333'))
        assert order.amount_total() == Decimal('99.99')
        assert _sql_total(order) == Decimal('99.99')


class TestSinFanOut:
    """La anotación es Subquery: una fila por orden, no una por línea."""

    def test_count_cuenta_ordenes_no_lineas(self, producto):
        o1 = _orden(producto)
        for _ in range(4):
            SaleOrderLine.objects.create(
                order=o1, product=producto, name='Prod E4',
                product_uom_qty=1, price_unit=Decimal('10.00'))
        o2 = _orden(producto)

        agg = with_amounts(
            SaleOrder.objects.filter(pk__in=[o1.pk, o2.pk])
        ).aggregate(revenue=Sum('amount_total_sql'), order_count=Count('id'))

        assert agg['order_count'] == 2                    # no 7
        assert agg['revenue'] == Decimal('240.00')        # 140 + 100
        assert agg['revenue'] == o1.amount_total() + o2.amount_total()


class TestDesgloseContribuidoPorCadaAddon:
    """Cada addon aporta su desglose con el motor de ``sale``.

    ``sale`` no sabe qué es una línea de envío ni una de recompensa — mismo
    reparto que la referencia, donde ``sale._compute_amounts`` suma todo y
    ``website_sale._compute_amount_delivery`` filtra ``is_delivery``.
    """

    def test_cada_addon_anota_su_importe_y_suman_al_total(
            self, producto, metodo):
        order = _orden(producto)
        order.carrier = metodo
        order.save(update_fields=['carrier', 'updated_at'])
        set_delivery_line(order, Decimal('99.00'))
        SaleOrderLine.objects.create(
            order=order, product=producto, name='Descuento',
            product_uom_qty=1, price_unit=Decimal('-20.00'), is_reward=True)

        qs = with_reward_amount(with_delivery_amount(
            with_amounts(SaleOrder.objects.filter(pk=order.pk))))
        row = qs.first()

        assert row.amount_delivery_sql == Decimal('99.00')
        assert row.amount_reward_sql == Decimal('-20.00')
        assert row.amount_total_sql == Decimal('179.00')
        assert row.amount_total_sql == order.amount_total()

    def test_sin_lineas_marcadas_los_desgloses_dan_cero(self, producto):
        order = _orden(producto)
        qs = with_reward_amount(with_delivery_amount(
            SaleOrder.objects.filter(pk=order.pk)))
        row = qs.first()
        assert row.amount_delivery_sql == Decimal('0.00')
        assert row.amount_reward_sql == Decimal('0.00')
