"""
Models — apps.voucher
Sprint 13 — UC-PRO-01/02/03/04, UC-CART-04

Voucher: cupon de descuento. Tres tipos: FIXED, PERCENTAGE, FREE_SHIPPING.
VoucherChangeLog: historial de cambios de admin (UC-PRO-02).
VoucherUsage: registro de uso por usuario — DEC-BC-10 T-301.
"""
from decimal import Decimal
from django.conf import settings
from django.db import models
from apps.core.models import SoftDeleteModel, TimeStampedModel
from django.core.validators import MinValueValidator
from django.utils import timezone



class Voucher(TimeStampedModel, SoftDeleteModel):
    """
    Cupon de descuento aplicable a un carrito.

    Coexisten dos semánticas de "borrado":

    - ``is_active`` / ``deactivated_at`` / ``deactivated_by``: desactivacion
      de NEGOCIO. El admin marca el cupon como no-usable (UC-PRO-03):
      sigue listado en reportes (UC-PRO-04) y en historiales de uso.
    - ``is_deleted`` / ``deleted_at`` (heredados de SoftDeleteModel,
      DEC-DOC-007): borrado LOGICO de SISTEMA. El admin removio la fila
      del listado operativo; queda fuera del manager por defecto pero
      recuperable via ``Voucher.all_objects`` para auditoria.

    Ambos campos son ortogonales: un voucher puede estar
    ``is_active=False`` (desactivado de negocio) e ``is_deleted=False``
    (todavia listable). Tambien puede llegar a ``is_deleted=True`` sin
    pasar por ``is_active=False`` si el admin descarta el registro
    directamente.
    """
    TYPE_FIXED        = 'FIXED'
    TYPE_PERCENTAGE   = 'PERCENTAGE'
    TYPE_FREE_SHIPPING = 'FREE_SHIPPING'
    TYPES = [
        (TYPE_FIXED,         'Descuento fijo'),
        (TYPE_PERCENTAGE,    'Porcentaje'),
        (TYPE_FREE_SHIPPING, 'Envio gratis'),
    ]

    code                = models.CharField(max_length=50, unique=True,
                              verbose_name='Codigo del cupon',
                              help_text='Siempre en mayusculas. Insensible a mayusculas en validacion.')
    voucher_type        = models.CharField(max_length=20, choices=TYPES, db_index=True)
    discount_value      = models.DecimalField(
                              max_digits=10, decimal_places=2,
                              null=True, blank=True,
                              validators=[MinValueValidator(Decimal('0.01'))],
                              verbose_name='Valor del descuento (FIXED)',
                              help_text='Importe fijo a descontar. Solo para tipo FIXED.')
    discount_pct        = models.DecimalField(
                              max_digits=5, decimal_places=2,
                              null=True, blank=True,
                              validators=[MinValueValidator(Decimal('0.01'))],
                              verbose_name='Porcentaje de descuento',
                              help_text='Porcentaje a descontar (0.01-100). Solo para tipo PERCENTAGE.')
    max_discount        = models.DecimalField(
                              max_digits=10, decimal_places=2,
                              null=True, blank=True,
                              verbose_name='Descuento maximo',
                              help_text='Tope para descuentos porcentuales. Null = sin tope.')
    min_order_amount    = models.DecimalField(
                              max_digits=10, decimal_places=2,
                              default=Decimal('0.00'),
                              validators=[MinValueValidator(Decimal('0.00'))],
                              verbose_name='Monto minimo del carrito',
                              help_text='El subtotal debe ser >= a este valor para aplicar el cupon.')
    max_uses            = models.PositiveIntegerField(
                              null=True, blank=True,
                              verbose_name='Usos maximos',
                              help_text='Null = ilimitado.')
    current_uses        = models.PositiveIntegerField(default=0,
                              verbose_name='Usos actuales')
    valid_from          = models.DateTimeField(verbose_name='Vigente desde')
    valid_until         = models.DateTimeField(null=True, blank=True,
                              verbose_name='Vigente hasta',
                              help_text='Null = sin fecha de expiracion.')
    is_active           = models.BooleanField(default=True, db_index=True)
    restricted_to_email = models.EmailField(null=True, blank=True,
                              verbose_name='Solo para este email',
                              help_text='Si se indica, solo ese email puede usar el cupon.')
    deactivated_at      = models.DateTimeField(null=True, blank=True)
    deactivated_by      = models.ForeignKey(
                              settings.AUTH_USER_MODEL,
                              null=True, blank=True,
                              on_delete=models.SET_NULL,
                              related_name='deactivated_vouchers',
                          )
    created_by          = models.ForeignKey(
                              settings.AUTH_USER_MODEL,
                              null=True, blank=True,
                              on_delete=models.SET_NULL,
                              related_name='created_vouchers',
                          )

    class Meta:
        db_table     = 'voucher_voucher'
        ordering     = ['-created_at']
        verbose_name = 'Voucher'

    def __str__(self):
        return f'{self.code} ({self.voucher_type})'

    def save(self, *args, **kwargs):
        self.code = self.code.upper()
        super().save(*args, **kwargs)

    def is_valid(self) -> bool:
        """Devuelve True si el voucher cumple todas las condiciones de vigencia y usos."""
        now = timezone.now()
        if not self.is_active:
            return False
        if now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        if self.max_uses is not None and self.current_uses >= self.max_uses:
            return False
        return True

    def validate_for_cart(self, subtotal: Decimal, user=None) -> str | None:
        """
        Valida el voucher para un carrito concreto.
        Retorna None si pasa, o un código de error string si falla.
        FR-CART-04.01.
        """
        now = timezone.now()
        if not self.is_active:
            return 'VOUCHER_INACTIVE'
        if now < self.valid_from:
            return 'VOUCHER_NOT_YET_ACTIVE'
        if self.valid_until and now > self.valid_until:
            return 'VOUCHER_EXPIRED'
        if self.max_uses is not None and self.current_uses >= self.max_uses:
            return 'VOUCHER_EXHAUSTED'
        if subtotal < self.min_order_amount:
            return 'MINIMUM_AMOUNT_NOT_REACHED'
        if self.restricted_to_email:
            if not user or not user.is_authenticated:
                return 'VOUCHER_REQUIRES_AUTHENTICATION'
            if user.email.lower() != self.restricted_to_email.lower():
                return 'VOUCHER_RESTRICTED_TO_OTHER_EMAIL'
        return None

    def calculate_discount(self, subtotal: Decimal) -> Decimal:
        """
        Calcula el descuento monetario sobre el subtotal.
        Para FREE_SHIPPING retorna 0 (el descuento es en el envío, no en el subtotal).
        FR-CART-04.02.
        """
        if self.voucher_type == self.TYPE_FIXED:
            return min(self.discount_value or Decimal('0'), subtotal)
        if self.voucher_type == self.TYPE_PERCENTAGE:
            raw = subtotal * (self.discount_pct or Decimal('0')) / Decimal('100')
            if self.max_discount is not None:
                raw = min(raw, self.max_discount)
            return raw.quantize(Decimal('0.01'))
        # FREE_SHIPPING
        return Decimal('0.00')


class VoucherChangeLog(TimeStampedModel):
    """
    Historial de cambios de administrador en un Voucher. UC-PRO-02.
    Un registro por cada edicion con el snapshot de campos modificados.
    """
    voucher    = models.ForeignKey(
        Voucher, on_delete=models.CASCADE, related_name='change_log',
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
    )
    changes    = models.JSONField(
        help_text='Dict de {campo: {before, after}} con los cambios aplicados.')
    # created_at viene de TimeStampedModel (renombrado de changed_at en migración)

    class Meta:
        db_table     = 'voucher_change_log'
        ordering     = ['-created_at']
        verbose_name = 'Cambio de voucher'

    def __str__(self):
        return f'{self.voucher.code} — {self.created_at.date()}'


class VoucherUsage(TimeStampedModel):
    """
    Registro de uso de un voucher por usuario. DEC-BC-10 T-301.
    UNIQUE(user, voucher) impide que el mismo usuario redima el
    cupon mas de una vez. created_at sirve como used_at.
    """
    user    = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='voucher_usages',
    )
    voucher = models.ForeignKey(
        Voucher, on_delete=models.CASCADE,
        related_name='usages',
    )

    class Meta:
        db_table        = 'voucher_usage'
        unique_together = [('user', 'voucher')]
        verbose_name    = 'Uso de voucher'

    def __str__(self):
        return f'{self.user_id} → {self.voucher.code}'
