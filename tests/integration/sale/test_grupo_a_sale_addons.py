"""Contratos del Grupo A de ``sale_*`` (#64) — los cuatro puentes portables.

Cada clase sella el comportamiento adaptado de su addon contra la semántica
de la fuente (``odoo19c:``, ``odoo-tools@622ddc2a``):

- ``sale_service`` — ``is_service`` deriva del tipo del producto; el dominio
  de servicios filtra por tipo y estado.
- ``sale_loyalty_delivery`` — el envío gratis vale el precio de la línea de
  envío acotado por ``max_discount`` (``_get_reward_values_free_shipping``).
- ``sale_stock_product_expiry`` — ``use_expiration_date`` es el related al
  producto; sin config es falso.
- ``sale_mrp_margin`` — el costo de un kit es la suma de sus componentes,
  normalizado por ``product_qty`` de la BoM.
"""
from decimal import Decimal

import pytest
from django.utils import timezone

from addons.loyalty.models.voucher import Voucher
from addons.mrp.models.mrp_bom import MrpBom, MrpBomLine
from addons.product.models.product_template import TYPE_SERVICE
from addons.sale.models.sale_order_line import SaleOrderLine
from addons.sale_loyalty.models.sale_order_coupon import SaleOrderCoupon
from addons.sale_loyalty_delivery.models.sale_order import (
    free_shipping_discount,
)
from addons.sale_margin.models.sale_order_line_margin import (
    SaleOrderLineMargin,
)
from addons.sale_mrp_margin.services import (
    bom_unit_cost,
    recompute_purchase_price_with_bom,
)
from addons.sale_service.models.sale_order_line import (
    is_service,
    service_lines,
)
from addons.sale_stock_product_expiry.models.sale_order_line import (
    use_expiration_date,
)
from tests.factories.order_factory import make_order
from tests.factories.product_factory import make_product

pytestmark = pytest.mark.django_db


@pytest.fixture
def orden():
    producto = make_product(name='Ofrenda', price='100.00')
    return make_order(product=producto, quantity=1, unit_price='100.00')


class TestSaleService:

    def test_is_service_deriva_del_tipo_del_producto(self, orden):
        linea = orden.order_line.first()
        assert is_service(linea) is False
        linea.product.product_tmpl.type = TYPE_SERVICE
        linea.product.product_tmpl.save(update_fields=['type'])
        linea.refresh_from_db()
        assert is_service(linea) is True

    def test_el_dominio_filtra_por_tipo_y_estado(self, orden):
        linea = orden.order_line.first()
        linea.product.product_tmpl.type = TYPE_SERVICE
        linea.product.product_tmpl.save(update_fields=['type'])
        # check_state=False: entra sin importar el estado de la orden.
        assert linea in service_lines(SaleOrderLine.objects.all(),
                                      check_state=False)
        # check_state=True: sólo órdenes confirmadas ('sale').
        confirmadas = service_lines(SaleOrderLine.objects.all())
        if orden.state != 'sale':
            assert linea not in confirmadas


class TestSaleLoyaltyDelivery:

    def _con_envio(self, orden, precio='50.00'):
        SaleOrderLine.objects.create(
            order=orden, product=orden.order_line.first().product,
            name='Envío estándar', price_unit=Decimal(precio),
            product_uom_qty=1, is_delivery=True,
        )

    def _con_cupon(self, orden, **voucher_kwargs):
        voucher = Voucher.objects.create(
            code='ENVIOGRATIS', voucher_type=Voucher.TYPE_FREE_SHIPPING,
            valid_from=timezone.now(), **voucher_kwargs,
        )
        SaleOrderCoupon.objects.create(order=orden, voucher=voucher)

    def test_el_envio_gratis_vale_el_precio_del_envio(self, orden):
        self._con_envio(orden, '50.00')
        self._con_cupon(orden)
        assert free_shipping_discount(orden) == Decimal('50.00')

    def test_max_discount_acota_como_en_la_fuente(self, orden):
        # -min(discount_max_amount, delivery.price_unit) de la fuente.
        self._con_envio(orden, '50.00')
        self._con_cupon(orden, max_discount=Decimal('30.00'))
        assert free_shipping_discount(orden) == Decimal('30.00')

    def test_sin_linea_de_envio_no_hay_descuento(self, orden):
        self._con_cupon(orden)
        assert free_shipping_discount(orden) == Decimal('0.00')

    def test_otro_tipo_de_cupon_no_descuenta_envio(self, orden):
        self._con_envio(orden, '50.00')
        voucher = Voucher.objects.create(
            code='DIEZ', voucher_type=Voucher.TYPE_FIXED,
            discount_value=Decimal('10.00'), valid_from=timezone.now(),
        )
        SaleOrderCoupon.objects.create(order=orden, voucher=voucher)
        assert free_shipping_discount(orden) == Decimal('0.00')


class TestSaleStockProductExpiry:
    """Actualizado con :ref:`h-api-576`: la configuración de caducidad vive en
    ``product.template`` (donde la referencia la declara), no en un modelo
    satélite ``ProductExpiryConfig`` que este puerto inventaba."""

    def test_sin_config_es_falso(self, orden):
        assert use_expiration_date(orden.order_line.first()) is False

    def test_el_related_lee_la_config_del_producto(self, orden):
        linea = orden.order_line.first()
        plantilla = linea.product.product_tmpl
        plantilla.tracking = 'lot'
        plantilla.use_expiration_date = True
        plantilla.save()
        linea.refresh_from_db()
        assert use_expiration_date(linea) is True


class TestSaleMrpMargin:

    def _kit_con_componentes(self, kit):
        # Kit (phantom) de 1 unidad con dos componentes: 2×30 + 1×15 = 75.
        bom = MrpBom.objects.create(
            type=MrpBom.TYPE_PHANTOM, product=kit,
            product_tmpl=kit.product_tmpl, product_qty=Decimal('1.00'),
        )
        comp_a = make_product(name='Componente A', price='60.00',
                              standard_price='30.00')
        comp_b = make_product(name='Componente B', price='40.00',
                              standard_price='15.00')
        MrpBomLine.objects.create(bom=bom, product=comp_a,
                                  product_qty=Decimal('2.00'))
        MrpBomLine.objects.create(bom=bom, product=comp_b,
                                  product_qty=Decimal('1.00'))

    def test_el_costo_del_kit_es_la_suma_de_componentes(self):
        kit = make_product(name='Kit ceremonial', price='200.00')
        self._kit_con_componentes(kit)
        assert bom_unit_cost(kit) == Decimal('75.00')

    def test_sin_bom_kit_no_hay_costo_derivado(self):
        suelto = make_product(name='Producto suelto', price='90.00')
        assert bom_unit_cost(suelto) is None

    def test_el_margen_usa_el_costo_de_bom(self, orden):
        linea = orden.order_line.first()
        self._kit_con_componentes(linea.product)
        cost = recompute_purchase_price_with_bom(linea)
        assert cost == Decimal('75.00')
        margen = SaleOrderLineMargin.objects.get(line=linea)
        assert margen.purchase_price == Decimal('75.00')
