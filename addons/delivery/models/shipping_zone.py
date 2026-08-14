"""Zona de cobertura de envío — ``ShippingZone`` (DEC-BC-18).

Vivía en ``addons/orders/models.py`` por historia, no por diseño: es dominio de
**entrega**, no de pedido. Su hermano natural ``ShippingMethod`` ya vive aquí,
junto con ``Courier`` y ``CarrierRateCard``. Rehubicada al detectar que retirar
el addon del espejo (E5) se la habría llevado por delante — ver H-API-46.

La tabla se renombra a ``delivery_shipping_zone``: el nombre ``orders_*`` era el
único rastro que quedaba de su domicilio anterior.
"""
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class ShippingZone(models.Model):
    """
    Zona de envío cubierta. DEC-BC-18.
    zip_code_prefix es el inicio del código postal cubierto (1-5 dígitos).
    Ejemplo: "44" cubre todos los CP que empiezan con "44" (Guadalajara, JAL).
    """
    name            = models.CharField(max_length=100)
    # Invariante (decision Nestor 2026-06-02): UNA zona por prefijo. unique=True
    # crea indice, asi que reemplaza al db_index. Ver H-API-07.
    zip_code_prefix = models.CharField(max_length=5, unique=True)
    is_active       = models.BooleanField(default=True)
    # H-12: catálogo de tiempos de entrega por zona. Ventana min/max de días
    # hábiles y costo opcional (vacío = usar el del método de envío). Nullable
    # para no forzar valores en zonas ya sembradas.
    estimated_days_min = models.PositiveSmallIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1)],
        help_text='Días hábiles mínimos de entrega en la zona.')
    estimated_days_max = models.PositiveSmallIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1)],
        help_text='Días hábiles máximos de entrega en la zona.')
    cost               = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal('0'))],
        help_text='Costo de envío específico de la zona. Vacío = usar el del método.')
    # G-ENV-01: umbral de envío GRATIS específico de la zona. Permite el modelo
    # tipo competidor (CDMX/Edomex gratis desde $800; nacional desde $1,300).
    # Vacío = usar el umbral del método de envío.
    free_threshold     = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal('0'))],
        help_text='Compra mínima para envío gratis en la zona. Vacío = usar el '
                  'del método de envío.')

    class Meta:
        db_table = 'delivery_shipping_zone'

    def __str__(self):
        return f'{self.name} ({self.zip_code_prefix})'

    @classmethod
    def resolve_for_zip(cls, zip_code):
        """G-ENV-01: zona activa más específica cuyo prefijo coincide con el
        inicio del C.P. (el prefijo más largo gana). None si ninguna cubre el
        C.P. o si viene vacío."""
        digits = ''.join(ch for ch in (zip_code or '') if ch.isdigit())
        if not digits:
            return None
        matches = [
            z for z in cls.objects.filter(is_active=True)
            if z.zip_code_prefix and digits.startswith(z.zip_code_prefix)
        ]
        if not matches:
            return None
        return max(matches, key=lambda z: len(z.zip_code_prefix))
