"""
Tests de la iniciativa: herencia-modelos-django
Verifica Fase 1 (TimeStampedModel) y Fase 2 (Proxy Models).

No son tests de integración de negocio — son tests de infraestructura
que garantizan que el refactoring no rompe nada.
"""
import pytest
from decimal import Decimal
from apps.core.models import TimeStampedModel
from apps.addons.cart.models import Cart, CartItem, SavedCart, SavedCartItem
from apps.addons.catalogue.models import Category, Product, SearchHistory, ProductImage
from apps.addons.chartsize.models import VariantType, VariantOption, ProductVariant
from apps.addons.inventory.models import StockMovement, StockAlert
from apps.addons.orders.models import Order, OrderItem, OrderValue, OrderAddress
from apps.addons.settings_app.models import SiteSettings, PaymentGateway, ShippingMethod, StaticPage, StaticPageVersion
from apps.addons.users.models import Address, PasswordResetToken, EmailVerificationToken
from apps.addons.users.models import IdentityUser as User
from apps.addons.voucher.models import Voucher, VoucherChangeLog
from apps.addons.wishlist.models import WishlistItem
from apps.addons.catalogue.serializers import SearchHistorySerializer
from apps.addons.inventory.proxy_models import SaleMovement, CancellationMovement, AdjustmentMovement, ImportMovement
from apps.addons.orders.proxy_models import PendingOrder, DeliveredOrder, ActiveOrder, CancelledOrder
from django.utils import timezone
from datetime import timedelta
from apps.addons.voucher.proxy_models import FixedVoucher, PercentageVoucher, FreeShippingVoucher

pytestmark = pytest.mark.integration


# =============================================================================
# Fase 1 — TimeStampedModel
# =============================================================================

class TestTimeStampedModelHerencia:
    """Todos los modelos concretos heredan de TimeStampedModel."""

    def test_todos_los_modelos_heredan_de_timestampedmodel(self, db):

        models_concretos = [
            Cart, CartItem, SavedCart, SavedCartItem,
            Category, Product, SearchHistory, ProductImage,
            VariantType, VariantOption, ProductVariant,
            StockMovement, StockAlert,
            Order, OrderItem, OrderValue, OrderAddress,
            SiteSettings, PaymentGateway, ShippingMethod,
            StaticPage, StaticPageVersion,
            Address, PasswordResetToken, EmailVerificationToken,
            Voucher, VoucherChangeLog,
            WishlistItem,
        ]
        for model in models_concretos:
            assert issubclass(model, TimeStampedModel), \
                f'{model.__name__} no hereda de TimeStampedModel'

    def test_user_NO_hereda_de_timestampedmodel(self, db):
        """DEC-005: User se excluye — hereda de AbstractUser de Django."""
        assert not issubclass(User, TimeStampedModel)

    def test_timestampedmodel_es_abstracto(self, db):
        """TimeStampedModel no debe crear tabla propia."""
        assert TimeStampedModel._meta.abstract is True

    def test_timestampedmodel_tiene_get_latest_by(self, db):
        assert TimeStampedModel._meta.get_latest_by == 'created_at'


class TestTimestampsEspeciales:
    """Casos especiales documentados en los hallazgos."""

    def test_h_inh_001_stockmovement_created_at_tiene_db_index(self, db):
        """H-INH-001 / DEC-003: override explícito en StockMovement."""
        field = StockMovement._meta.get_field('created_at')
        assert field.db_index is True

    def test_h_inh_001_stockalert_created_at_tiene_db_index(self, db):
        """DEC-003: override explícito en StockAlert."""
        field = StockAlert._meta.get_field('created_at')
        assert field.db_index is True

    def test_h_inh_001_order_created_at_tiene_db_index(self, db):
        """DEC-003: override explícito en Order."""
        field = Order._meta.get_field('created_at')
        assert field.db_index is True

    def test_h_inh_002_searchhistory_campo_externo_es_searched_at(self, db):
        """
        H-INH-002: SearchHistory.searched_at → updated_at internamente.
        El serializer expone 'searched_at' via source='updated_at'.
        """
        s = SearchHistorySerializer()
        assert 'searched_at' in s.fields
        field = s.fields['searched_at']
        assert field.source == 'updated_at'

    def test_h_inh_002_searchhistory_no_tiene_campo_searched_at_en_bd(self, db):
        """searched_at ya no es un campo del modelo."""
        field_names = [f.name for f in SearchHistory._meta.get_fields()]
        assert 'searched_at' not in field_names
        assert 'updated_at' in field_names
        assert 'created_at' in field_names

    def test_h_inh_003_voucherchangelog_campo_es_created_at(self, db):
        """H-INH-003: VoucherChangeLog.changed_at renombrado a created_at."""
        field_names = [f.name for f in VoucherChangeLog._meta.get_fields()]
        assert 'changed_at' not in field_names
        assert 'created_at' in field_names
        assert 'updated_at' in field_names

    def test_h_inh_004_sitesettings_tiene_created_at(self, db):
        """H-INH-004: SiteSettings solo tenía updated_at — ahora tiene ambos."""
        field_names = [f.name for f in SiteSettings._meta.get_fields()]
        assert 'created_at' in field_names
        assert 'updated_at' in field_names

    def test_h_inh_005_savedcart_tiene_created_at_y_updated_at(self, db):
        """H-INH-005: SavedCart.saved_at renombrado a updated_at + ADD created_at."""
        field_names = [f.name for f in SavedCart._meta.get_fields()]
        assert 'saved_at' not in field_names
        assert 'updated_at' in field_names
        assert 'created_at' in field_names


# =============================================================================
# Fase 2 — Proxy Models
# =============================================================================

class TestStockMovementProxies:
    """T-012: proxy models para StockMovement."""

    def test_proxy_models_no_crean_tablas(self, db):
        for proxy in [SaleMovement, CancellationMovement, AdjustmentMovement, ImportMovement]:
            assert proxy._meta.db_table == StockMovement._meta.db_table
            assert proxy._meta.proxy is True

    def test_sale_movement_filtra_por_tipo(self, db):

        cat = Category.objects.create(name='CP', slug='cp', is_active=True)
        p = Product.objects.create(
            name='PP', slug='pp', sku='PP-001', description='',
            price=Decimal('100'), stock=10,
            is_active=True, is_published=True,
        )
        p.categories.add(cat)
        p.categories.add(cat)
        StockMovement.objects.create(
            product=p, delta=-2, stock_after=8,
            movement_type=StockMovement.TYPE_SALE,
        )
        StockMovement.objects.create(
            product=p, delta=5, stock_after=13,
            movement_type=StockMovement.TYPE_ADJUSTMENT,
        )
        assert SaleMovement.objects.filter(product=p).count() == 1
        assert AdjustmentMovement.objects.filter(product=p).count() == 1
        assert SaleMovement.objects.filter(product=p).first().movement_type == 'SALE'


class TestOrderProxies:
    """T-013: proxy models para Order."""

    def test_proxy_models_no_crean_tablas(self, db):
        for proxy in [PendingOrder, DeliveredOrder, ActiveOrder]:
            assert proxy._meta.db_table == Order._meta.db_table
            assert proxy._meta.proxy is True

    def test_pending_order_filtra_por_estado(self, db):

        o1 = Order.objects.create(status=Order.STATUS_PENDING)
        o2 = Order.objects.create(status=Order.STATUS_CANCELLED)

        assert PendingOrder.objects.count() == 1
        assert CancelledOrder.objects.count() == 1

    def test_active_order_incluye_multiples_estados(self, db):

        Order.objects.create(status=Order.STATUS_PENDING)
        Order.objects.create(status=Order.STATUS_PROCESSING)
        Order.objects.create(status=Order.STATUS_DELIVERED)  # no activa

        assert ActiveOrder.objects.count() == 2


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
