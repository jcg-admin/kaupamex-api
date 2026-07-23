"""
Proxy models — addons.loyalty
Sprint de infraestructura: herencia-modelos-django (T-014)

Tipo de herencia: PROXY (DEC-006).
- Misma tabla: voucher_voucher
- Sin migraciones nuevas
- Open/Closed: cada tipo tiene su propia implementación de calculate_discount()
  El if/elif original de Voucher.calculate_discount() se mantiene como
  fallback en la clase base pero ahora puede delegarse al proxy correcto.

Uso:
    from addons.loyalty.proxy_models import FixedVoucher, PercentageVoucher
    v = FixedVoucher.objects.get(code='PROMO50')
    descuento = v.calculate_discount(subtotal)

Cómo instanciar el proxy correcto desde una instancia base:
    voucher = Voucher.objects.get(code='...')
    proxy   = voucher.as_typed()  # retorna FixedVoucher, PercentageVoucher, etc.
"""
from decimal import Decimal
from django.db import models
from .models import Voucher



# =============================================================================
# Managers
# =============================================================================

class FixedVoucherManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(voucher_type=Voucher.TYPE_FIXED)


class PercentageVoucherManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(voucher_type=Voucher.TYPE_PERCENTAGE)


class FreeShippingVoucherManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(voucher_type=Voucher.TYPE_FREE_SHIPPING)


# =============================================================================
# Proxy Models con calculate_discount() especializado
# =============================================================================

class FixedVoucher(Voucher):
    """
    Voucher de descuento fijo.
    calculate_discount() = min(discount_value, subtotal).
    """
    objects = FixedVoucherManager()

    class Meta:
        proxy        = True
        verbose_name = 'Voucher de descuento fijo'

    def calculate_discount(self, subtotal: Decimal) -> Decimal:
        return min(self.discount_value or Decimal('0'), subtotal)

    def save(self, *args, **kwargs):
        self.voucher_type = Voucher.TYPE_FIXED
        super().save(*args, **kwargs)


class PercentageVoucher(Voucher):
    """
    Voucher de descuento porcentual con tope opcional.
    calculate_discount() aplica el porcentaje con límite max_discount.
    """
    objects = PercentageVoucherManager()

    class Meta:
        proxy        = True
        verbose_name = 'Voucher de porcentaje'

    def calculate_discount(self, subtotal: Decimal) -> Decimal:
        raw = subtotal * (self.discount_pct or Decimal('0')) / Decimal('100')
        if self.max_discount is not None:
            raw = min(raw, self.max_discount)
        return raw.quantize(Decimal('0.01'))

    def save(self, *args, **kwargs):
        self.voucher_type = Voucher.TYPE_PERCENTAGE
        super().save(*args, **kwargs)


class FreeShippingVoucher(Voucher):
    """
    Voucher de envío gratis.
    calculate_discount() retorna 0 (el beneficio se aplica en shipping_cost).
    """
    objects = FreeShippingVoucherManager()

    class Meta:
        proxy        = True
        verbose_name = 'Voucher de envío gratis'

    def calculate_discount(self, subtotal: Decimal) -> Decimal:
        # El descuento monetario en subtotal es 0.
        # El beneficio se refleja en Cart.get_totals() → free_shipping_applied = True
        return Decimal('0.00')

    def save(self, *args, **kwargs):
        self.voucher_type = Voucher.TYPE_FREE_SHIPPING
        super().save(*args, **kwargs)


# =============================================================================
# Helper en el modelo base — factory method
# =============================================================================

def _as_typed(self) -> 'FixedVoucher | PercentageVoucher | FreeShippingVoucher':
    """
    Retorna la instancia como el proxy correcto según voucher_type.
    Útil cuando tienes un Voucher genérico y necesitas el comportamiento
    específico del tipo.

    Ejemplo:
        v = Voucher.objects.get(code='...')
        typed = v.as_typed()
        descuento = typed.calculate_discount(subtotal)
    """
    TYPE_MAP = {
        Voucher.TYPE_FIXED:         FixedVoucher,
        Voucher.TYPE_PERCENTAGE:    PercentageVoucher,
        Voucher.TYPE_FREE_SHIPPING: FreeShippingVoucher,
    }
    proxy_cls = TYPE_MAP.get(self.voucher_type, Voucher)
    self.__class__ = proxy_cls
    return self


# Monkey-patch en el modelo base (no requiere migración)
Voucher.as_typed = _as_typed
