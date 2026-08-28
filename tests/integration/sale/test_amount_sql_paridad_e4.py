"""Tests — E4/H-API-30: ``amount_total`` materializado como columna.

Hasta H-API-30 el dinero de la orden eran métodos Python
(``SaleOrder.amount_total()``), y SQL no puede ``Sum()`` un método — de ahí el
shim ``AMOUNT_TOTAL_SQL``/``with_amounts`` que este archivo fijaba por
paridad. La materialización (``amount_untaxed``/``amount_tax``/``amount_total``
como columnas ``fields.Monetary``, Odoo ``sale/models/sale_order.py:232-234``)
retira ese shim: un ``Sum('amount_total')`` agrega directo, sin subquery ni
riesgo de fan-out, porque ya no hay nada que aproximar.

Lo que se fija aquí, con la nueva premisa:

1. La columna se **recalcula y persiste** cuando cambian las líneas de la
   orden (crear, editar cantidad/descuento, borrar) — disparado desde
   ``SaleOrderLine.save()``/``delete()`` (equivalente Django del
   ``@api.depends`` de la referencia).
2. Preserva el redondeo **por línea**, no al final — mismo caso adverso de
   antes (tres líneas de ``33.333``).
3. Agrega con ``Sum`` directo sobre el queryset de ``SaleOrder``: sin
   subquery, sin fan-out (un ``Count('id')`` en el mismo ``aggregate()``
   sigue contando órdenes, nunca líneas — ya no hay join a línea que lo
   arriesgue).
4. Una orden recién creada, sin líneas, tiene ``0.00`` — nunca ``NULL``: es
   el ``default=Decimal('0.00')`` del campo, no un cómputo que deba blindarse
   contra ausencia de filas.
"""
from decimal import Decimal
from uuid import uuid4

import pytest
from django.db.models import Count, Sum

from addons.delivery.aggregates import with_delivery_amount
from addons.delivery.models import ShippingMethod
from addons.delivery.models.sale_order import set_delivery_line
from addons.sale.models import SaleOrder, SaleOrderLine
from addons.sale_loyalty.aggregates import with_reward_amount
from tests.factories.product_factory import make_category, make_product

pytestmark = pytest.mark.django_db


@pytest.fixture
def producto():
    cat = make_category(name='Cat E4')
    return make_product(name='Prod E4', price=Decimal('100.00'), stock=99, categ=cat)


@pytest.fixture
def metodo():
    return ShippingMethod.objects.create(
        name='Estándar E4', cost=Decimal('99.00'), estimated_days=3)


def _order(producto, **line_kwargs):
    order = SaleOrder.objects.create(
        state=SaleOrder.STATE_DRAFT, cart_token=uuid4())
    defaults = {'product_uom_qty': 1, 'price_unit': Decimal('100.00'),
                'name': 'Prod E4'}
    defaults.update(line_kwargs)
    SaleOrderLine.objects.create(order=order, product=producto, **defaults)
    return order


class TestLaColumnaSeRecalculaAlCambiarLineas:

    def test_orden_recien_creada_da_cero_no_null(self):
        order = SaleOrder.objects.create(
            state=SaleOrder.STATE_DRAFT, cart_token=uuid4())
        assert order.amount_total is not None
        assert order.amount_total == Decimal('0.00')
        assert order.amount_untaxed == Decimal('0.00')
        assert order.amount_tax == Decimal('0.00')

    def test_crear_una_linea_recalcula_el_total(self, producto):
        order = _order(producto)
        assert order.amount_total == Decimal('100.00')

    def test_con_cantidad_y_descuento_de_linea(self, producto):
        order = _order(producto, product_uom_qty=3, discount=Decimal('10.00'))
        assert order.amount_total == Decimal('270.00')

    def test_editar_la_cantidad_recalcula_el_total(self, producto):
        order = _order(producto)
        linea = order.order_line.get()
        linea.product_uom_qty = 3
        linea.save(update_fields=['product_uom_qty', 'updated_at'])
        assert order.amount_total == Decimal('300.00')

    def test_borrar_la_linea_recalcula_a_cero(self, producto):
        order = _order(producto)
        assert order.amount_total == Decimal('100.00')
        order.order_line.get().delete()
        assert order.amount_total == Decimal('0.00')

    def test_persiste_en_bd_no_solo_en_memoria(self, producto):
        order = _order(producto)
        recargada = SaleOrder.objects.get(pk=order.pk)
        assert recargada.amount_total == Decimal('100.00')

    def test_with_line_of_shipping(self, producto, metodo):
        order = _order(producto)
        order.carrier = metodo
        order.save(update_fields=['carrier', 'updated_at'])
        set_delivery_line(order, Decimal('99.00'))
        assert order.amount_total == Decimal('199.00')

    def test_con_linea_de_recompensa_negativa(self, producto):
        order = _order(producto)
        SaleOrderLine.objects.create(
            order=order, product=producto, name='Descuento',
            product_uom_qty=1, price_unit=Decimal('-20.00'), is_reward=True)
        assert order.amount_total == Decimal('80.00')


class TestRedondeoPorLinea:
    """La columna cuantiza por línea, no al final (mismo caso adverso E4).

    Con tres líneas de ``33.333``: redondear por línea da 33.33×3 = 99.99;
    sumar exacto y redondear al final daría 100.00. Un centavo de diferencia
    por orden es suficiente para descuadrar un reporte de ingresos, así que
    la estrategia no puede quedar implícita.
    """

    def test_cuantiza_por_linea_no_al_final(self, producto):
        order = SaleOrder.objects.create(
            state=SaleOrder.STATE_DRAFT, cart_token=uuid4())
        for _ in range(3):
            SaleOrderLine.objects.create(
                order=order, product=producto, name='Prod E4',
                product_uom_qty=1, price_unit=Decimal('33.333'))
        assert order.amount_total == Decimal('99.99')


class TestSinFanOut:
    """``Sum`` directo sobre la columna: una fila por orden, sin subquery."""

    def test_count_cuenta_ordenes_no_lineas(self, producto):
        o1 = _order(producto)
        for _ in range(4):
            SaleOrderLine.objects.create(
                order=o1, product=producto, name='Prod E4',
                product_uom_qty=1, price_unit=Decimal('10.00'))
        o2 = _order(producto)

        agg = SaleOrder.objects.filter(pk__in=[o1.pk, o2.pk]).aggregate(
            revenue=Sum('amount_total'), order_count=Count('id'))

        assert agg['order_count'] == 2                    # no 7
        assert agg['revenue'] == Decimal('240.00')        # 140 + 100
        assert agg['revenue'] == o1.amount_total + o2.amount_total


class TestDesgloseContribuidoPorCadaAddon:
    """Cada addon aporta su desglose de línea; ``sale`` sólo aporta la columna.

    ``sale`` no sabe qué es una línea de envío ni una de recompensa — mismo
    reparto que la referencia, donde ``sale._compute_amounts`` suma todo y
    ``website_sale._compute_amount_delivery`` filtra ``is_delivery``. El
    desglose de ``delivery``/``sale_loyalty`` sigue siendo un ``Subquery``
    (necesitan filtrar un subconjunto de líneas); el total de la orden ya no.
    """

    def test_cada_addon_anota_su_importe_y_suman_al_total(
            self, producto, metodo):
        order = _order(producto)
        order.carrier = metodo
        order.save(update_fields=['carrier', 'updated_at'])
        set_delivery_line(order, Decimal('99.00'))
        SaleOrderLine.objects.create(
            order=order, product=producto, name='Descuento',
            product_uom_qty=1, price_unit=Decimal('-20.00'), is_reward=True)

        qs = with_reward_amount(with_delivery_amount(
            SaleOrder.objects.filter(pk=order.pk)))
        row = qs.first()

        assert row.amount_delivery_sql == Decimal('99.00')
        assert row.amount_reward_sql == Decimal('-20.00')
        assert row.amount_total == Decimal('179.00')
        assert row.amount_total == order.amount_total

    def test_sin_lineas_marcadas_los_desgloses_dan_cero(self, producto):
        order = _order(producto)
        qs = with_reward_amount(with_delivery_amount(
            SaleOrder.objects.filter(pk=order.pk)))
        row = qs.first()
        assert row.amount_delivery_sql == Decimal('0.00')
        assert row.amount_reward_sql == Decimal('0.00')


class TestBackfillDeOrdenesPreexistentes:
    """La migración de backfill deja las órdenes ya creadas con su total real.

    Simula el escenario que la migración ``RunPython`` resuelve: una fila
    creada sin pasar por ``_compute_amounts()`` (aquí, escribiendo el campo
    directo vía ``update()`` a nivel queryset para no disparar el compute)
    debe terminar con el mismo total que arroja recalcularla a mano — la
    misma operación que ejecuta el backfill fila por fila.
    """

    def test_recalculo_manual_coincide_con_la_orden_ya_computada(
            self, producto):
        with_compute = _order(producto, product_uom_qty=2,
                              discount=Decimal('10.00'))
        # Fuerza la columna a un valor "stale" sin pasar por el compute —
        # reproduce el estado de una fila pre-existente antes del backfill.
        SaleOrder.objects.filter(pk=with_compute.pk).update(
            amount_total=Decimal('0.00'), amount_untaxed=Decimal('0.00'),
            amount_tax=Decimal('0.00'))
        with_compute.refresh_from_db()
        assert with_compute.amount_total == Decimal('0.00')

        # El backfill hace exactamente esto: recorrer la orden y recalcular.
        with_compute._compute_amounts()
        assert with_compute.amount_total == Decimal('180.00')
