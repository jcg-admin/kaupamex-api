"""
Tests de la iniciativa: herencia-modelos-django
Verifica Fase 1 (TimeStampedModel) y Fase 2 (Proxy Models).

No son tests de integración de negocio — son tests de infraestructura
que garantizan que el refactoring no rompe nada.

Nota (retiro del espejo ``orders.Order``, SOL-098, ``api@77bd1f0``): la
antigua ``TestOrderProxies`` ejercía los proxies ``DeliveredOrder``/
``ActiveOrder`` de ese addon retirado — ninguno de los dos existe ya en
``src/`` (los seis proxies restantes ya se habían eliminado antes, H-API-06).
Sin el modelo espejo, el caso ya no tiene sujeto: se borró en vez de
reencuadrarse, porque su reemplazo funcional (derivar estado desde
``sale.state``/pago/guía sin proxy dedicado) ya está cubierto en
``tests/integration/sale/test_proxy_replacement_e5r5.py``, fuera de este
archivo.

Nota (disolución de ``catalogue``/``chartsize``/``inventory``/``cart``,
H-API-250): cuatro de los addons que este archivo inventariaba ya no existen
(``ls src/addons/{catalogue,chartsize,inventory,cart}`` → *No such file or
directory*). Se retiraron los casos cuyo **sujeto** desapareció:

- ``TestStockMovementProxies`` entero — los proxies vivían en
  ``inventory.proxy_models``; el movimiento de stock ahora es
  ``stock.quant``/``stock.move`` (odoo19c), sin proxies por tipo.
- ``test_h_inh_001_{stockmovement,stockalert}_...`` — ídem ``inventory``.
- ``test_h_inh_002_searchhistory_*`` — ``SearchHistory`` no tiene sucesor: la
  referencia no modela historial de búsqueda (el único análogo en ``odoo19c:``
  es un mixin de ``website``, no un modelo).
- ``test_h_inh_005_savedcart_*`` — ``cart`` disuelto; el carrito es una
  ``sale.order`` en borrador (odoo19c).

El inventario de herencia conserva los modelos vivos y **suma** los sucesores
del catálogo (``ProductTemplate``/``ProductProduct``/``ProductCategory``), que
sí heredan ``TimeStampedModel``. Se retiran además los símbolos de
``addons.users`` (disuelto: ``res.users`` vive en ``base``) y con ellos
``test_user_NO_hereda_de_timestampedmodel``, cuya premisa se invierte —
``base.ResUsers`` **sí** hereda ``TimeStampedModel`` (``res_users.py:148``).
"""
import pytest
from decimal import Decimal
from addons.base.models import TimeStampedModel
from addons.product.models import ProductCategory, ProductProduct, ProductTemplate
from addons.delivery.models import ShippingMethod
from addons.payment.models import PaymentGateway
from addons.website.models import StaticPage, StaticPageVersion
from addons.loyalty.models import Voucher, VoucherChangeLog
from addons.website_sale_wishlist.models import WishlistItem
from addons.sale.models import SaleOrder, SaleOrderLine
from addons.delivery.models import DeliveryAddress
from django.utils import timezone
from datetime import timedelta
from addons.loyalty.proxy_models import FixedVoucher, PercentageVoucher, FreeShippingVoucher

pytestmark = pytest.mark.integration


# =============================================================================
# Fase 1 — TimeStampedModel
# =============================================================================

class TestTimeStampedModelHerencia:
    """Todos los modelos concretos heredan de TimeStampedModel."""

    def test_todos_los_modelos_heredan_de_timestampedmodel(self, db):

        models_concretos = [
            ProductCategory, ProductTemplate, ProductProduct,
            SaleOrder, SaleOrderLine, DeliveryAddress,
            PaymentGateway, ShippingMethod,
            StaticPage, StaticPageVersion,
            Voucher, VoucherChangeLog,
            WishlistItem,
        ]
        for model in models_concretos:
            assert issubclass(model, TimeStampedModel), \
                f'{model.__name__} no hereda de TimeStampedModel'

    def test_timestampedmodel_es_abstracto(self, db):
        """TimeStampedModel no debe crear tabla propia."""
        assert TimeStampedModel._meta.abstract is True

    def test_timestampedmodel_tiene_get_latest_by(self, db):
        assert TimeStampedModel._meta.get_latest_by == 'created_at'


class TestTimestampsEspeciales:
    """Casos especiales documentados en los hallazgos."""

    def test_h_inh_001_order_created_at_tiene_db_index(self, db):
        """DEC-003: override explícito en SaleOrder."""
        field = SaleOrder._meta.get_field('created_at')
        assert field.db_index is True

    def test_h_inh_003_voucherchangelog_campo_es_created_at(self, db):
        """H-INH-003: VoucherChangeLog.changed_at renombrado a created_at."""
        field_names = [f.name for f in VoucherChangeLog._meta.get_fields()]
        assert 'changed_at' not in field_names
        assert 'created_at' in field_names
        assert 'updated_at' in field_names

    # H-INH-004 verificaba que ``SiteSettings`` tuviera ambos timestamps. Esa
    # tabla se retiró (H-API-265): los ajustes ya no son una fila, son claves
    # de parámetro, y ``SystemParameter`` trae sus propios timestamps —
    # cubiertos por el caso de arriba. El hallazgo queda cerrado por
    # desaparición del sujeto, no por regresión.


# =============================================================================
# Fase 2 — Proxy Models
# =============================================================================

class TestVoucherProxies:
    """T-014: proxy models para Voucher con calculate_discount especializado."""

    def _base_voucher_data(self):
        return {'valid_from': timezone.now() - timedelta(days=1),
                'min_order_amount': Decimal('0'), 'is_active': True}

    def test_proxy_models_no_crean_tablas(self, db):
        for proxy in [FixedVoucher, PercentageVoucher, FreeShippingVoucher]:
            assert proxy._meta.db_table == Voucher._meta.db_table
            assert proxy._meta.proxy is True

    def test_fixed_voucher_calculate_discount(self, db):
        v = FixedVoucher(**self._base_voucher_data(),
                         code='FIX50', discount_value=Decimal('50'))
        assert v.calculate_discount(Decimal('200')) == Decimal('50')
        assert v.calculate_discount(Decimal('30')) == Decimal('30')  # min

    def test_percentage_voucher_con_tope(self, db):
        v = PercentageVoucher(**self._base_voucher_data(),
                              code='PCT15', discount_pct=Decimal('15'),
                              max_discount=Decimal('100'))
        assert v.calculate_discount(Decimal('1000')) == Decimal('100')  # tope
        assert v.calculate_discount(Decimal('400')) == Decimal('60.00')  # 15%

    def test_free_shipping_voucher_retorna_cero(self, db):
        v = FreeShippingVoucher(**self._base_voucher_data(), code='FREE')
        assert v.calculate_discount(Decimal('500')) == Decimal('0.00')

    def test_as_typed_retorna_proxy_correcto(self, db):

        v_fixed = Voucher(code='TF', voucher_type=Voucher.TYPE_FIXED,
                          discount_value=Decimal('50'),
                          valid_from=timezone.now(), is_active=True,
                          min_order_amount=Decimal('0'))
        assert isinstance(v_fixed.as_typed(), FixedVoucher)

        v_pct = Voucher(code='TP', voucher_type=Voucher.TYPE_PERCENTAGE,
                        discount_pct=Decimal('10'),
                        valid_from=timezone.now(), is_active=True,
                        min_order_amount=Decimal('0'))
        assert isinstance(v_pct.as_typed(), PercentageVoucher)

    def test_fixed_voucher_manager_filtra_correctamente(self, db):

        data = {'valid_from': timezone.now(), 'is_active': True,
                'min_order_amount': Decimal('0')}

        Voucher.objects.create(code='F1', voucher_type='FIXED',
                               discount_value=Decimal('10'), **data)
        Voucher.objects.create(code='P1', voucher_type='PERCENTAGE',
                               discount_pct=Decimal('5'), **data)

        assert FixedVoucher.objects.count() == 1
        assert PercentageVoucher.objects.count() == 1
