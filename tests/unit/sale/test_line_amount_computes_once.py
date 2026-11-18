"""Los importes de una línea de venta se calculan una vez por operación.

≙ ``odoo19c: addons/sale/models/sale_order_line.py:190-209``: las cinco
cantidades son ``store=True, precompute=True`` y ``create`` (``:1322``) no
las toca; las calcula ``_add_precomputed_values`` antes del INSERT. Aquí
``SaleOrderLine.save`` las invocaba además por su cuenta, así que el alta
las calculaba dos veces. La modificación con ``update_fields`` no duplica y
tiene consumidores que leen la columna sin volcar (``addons/sale/
services.py:249`` y ``:400``). designs/eager-computes-in-save.md.

Se lee ``price_total`` y no ``price_subtotal``: sin impuestos en la línea,
la fuente da a los dos el producto de precio y cantidad, pero este árbol
todavía extrae el IVA de un precio con IVA incluido aunque la línea no lleve
impuestos (divergencia declarada en ``SaleOrderLine``, tarea #141), y el
subtotal saldría 155,17. El total no depende de esa divergencia.

El caso de alta discrimina: si ``save`` vuelve a calcular en alta, el
recuento pasa a dos. El de modificación no distingue la rama de ``save``
que recalcula: sin ella la columna se escribe igual, porque leer el campo
durante el guardado dispara el recálculo pendiente del ORM, como en la
fuente. Mide el contrato —la columna correcta en el mismo ``save``—, no la
rama.
"""
from decimal import Decimal

import pytest
from django.db import connection

from addons.sale.models import SaleOrderLine
from tests.factories.order_factory import make_order
from tests.factories.product_factory import make_product

pytestmark = pytest.mark.django_db


@pytest.fixture
def amount_calls(monkeypatch):
    calls = []
    original = SaleOrderLine._compute_amount

    def counting(self):
        calls.append(self.pk)
        return original(self)

    monkeypatch.setattr(SaleOrderLine, '_compute_amount', counting)
    return calls


@pytest.fixture
def order(user):
    return make_order(user=user)


def test_creation_computes_the_amounts_once(order, amount_calls):
    product = make_product(name='Hora')
    line = SaleOrderLine.objects.create(
        order=order, product=product, name=product.name,
        price_unit=Decimal('90.00'), product_uom_qty=2)
    assert len(amount_calls) == 1
    row = SaleOrderLine.objects.values('price_total').get(pk=line.pk)
    assert row['price_total'] == Decimal('180.00')


def test_a_partial_update_writes_the_amounts_in_the_same_save(order):
    product = make_product(name='Hora')
    line = SaleOrderLine.objects.create(
        order=order, product=product, name=product.name,
        price_unit=Decimal('90.00'), product_uom_qty=2)
    line.price_unit = Decimal('100.00')
    line.save(update_fields=['price_unit', 'write_date'])
    # SQL directo: lo que lee un consumidor que no vuelca los cálculos
    # pendientes del ORM. Una lectura por el ORM los volcaría antes.
    with connection.cursor() as cursor:
        cursor.execute('SELECT price_total FROM sale_order_line '
                       'WHERE id = %s', [line.pk])
        assert cursor.fetchone() == (Decimal('200.00'),)
