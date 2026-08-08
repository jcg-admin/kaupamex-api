"""``Voucher`` — cupón de descuento (UC-PRO-01/02/03/04, UC-CART-04).

Tres tipos: FIXED, PERCENTAGE, FREE_SHIPPING. Incluye la maquinaria de
generación de sufijo del código.

SIN contraparte 1:1 en ``odoo19c: loyalty/models/`` (allí el dominio es
loyalty_program/card/reward/rule); el porte semántico de esa familia es una
iniciativa aparte — ver el mapa en ``__init__.py``.
"""
import logging
import secrets
import string
from decimal import Decimal

from django.apps import apps
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.utils import timezone

from addons.base.models import SoftDeleteModel, TimeStampedModel

logger = logging.getLogger('apps')

_ALPHABET = string.ascii_uppercase + string.digits


def generate_suffix(length: int = 6) -> str:
    """Genera un sufijo aleatorio de ``length`` caracteres en mayusculas."""
    return ''.join(secrets.choice(_ALPHABET) for _ in range(length))

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
    TYPE_REFERRAL     = 'REFERRAL'
    TYPES = [
        (TYPE_FIXED,         'Descuento fijo'),
        (TYPE_PERCENTAGE,    'Porcentaje'),
        (TYPE_FREE_SHIPPING, 'Envio gratis'),
        (TYPE_REFERRAL,      'Codigo referral'),
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
                              validators=[MinValueValidator(Decimal('0.01')),
                                          MaxValueValidator(Decimal('100.00'))],
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

    # ------------------------------------------------------------------
    # Caducidad — el método que el cron invoca (UC-SYS-02)
    # ------------------------------------------------------------------

    @classmethod
    def expire_overdue(cls):
        """Desactiva los vouchers vencidos y registra el cambio. Devuelve cuántos.

        Vivía como función suelta en ``addons.loyalty.tasks``, invocada sólo por
        un management command. ``ir.cron`` resuelve ``<model>.<method>()``, no
        módulos ni comandos, así que el registro de horario no tenía a qué
        apuntar. La lógica es la misma; cambia su hogar.

        Dos candados, ambos con su hallazgo:

        - ``skip_locked`` (H-VOUCHER-01) — dos crons concurrentes no procesan el
          mismo voucher ni duplican su entrada de bitácora.
        - re-chequeo de ``valid_until`` **dentro** del candado (H-CICLO125-02) —
          la lista inicial se lee sin bloquear; si un administrador extiende la
          vigencia entre esa lectura y el candado, sin este guard el voucher se
          caducaría igual. Cierra la ventana TOCTOU.
        """
        # apps.get_model, no un import: ``voucher_change_log`` importa Voucher
        # (voucher_change_log.py:6), así que el import al top sería un ciclo
        # REAL — verificado, no supuesto. La excepción #3 de no-lazy-imports
        # prohíbe resolverlo con un import diferido; esto es una **llamada**,
        # el mismo mecanismo sancionado que importlib en AppConfig.ready().
        VoucherChangeLog = apps.get_model('loyalty', 'VoucherChangeLog')

        now = timezone.now()
        vencidos = list(
            cls.objects.filter(is_active=True, valid_until__lt=now)
            .values_list('id', flat=True)
        )
        contados = 0
        for voucher_id in vencidos:
            with transaction.atomic():
                actualizado = cls.objects.filter(
                    pk=voucher_id, is_active=True, valid_until__lt=now
                ).select_for_update(skip_locked=True).first()
                if actualizado is None:
                    continue
                actualizado.is_active = False
                actualizado.deactivated_at = now
                actualizado.save(
                    update_fields=['is_active', 'deactivated_at', 'updated_at']
                )
                VoucherChangeLog.objects.create(
                    voucher=actualizado,
                    changed_by=None,
                    changes={
                        'is_active': {'before': True, 'after': False},
                        'source': 'AUTOMATIC_EXPIRATION',
                        'deactivated_at': str(now),
                    },
                )
                contados += 1
        if contados:
            logger.info('expire_overdue: %d vouchers expirados.', contados)
        return contados
