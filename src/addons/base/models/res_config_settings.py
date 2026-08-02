"""``SiteSettings`` — la configuración operativa del sitio, tipada y persistente.

**Corregido** (porte de ``res_config.py``). Este docstring se declaraba
*"contraparte de ``res.config.settings``"*. **No lo es**, y la diferencia
importa porque las dos piezas ya coexisten:

- ``res.config.settings`` (portado en ``res_config.py``) es un formulario
  **transitorio** cuyos campos se interpretan **por su nombre**
  (``default_`` / ``group_`` / ``module_`` / ``config_parameter``) y cuyo
  efecto se escribe en **otros** sitios: ``ir.default``, los grupos, los
  parámetros de sistema. No guarda nada en sí mismo.
- ``SiteSettings`` es una fila **persistente y tipada** —identidad del sitio,
  IVA, umbrales, timeouts, contacto (UC-CFG-03)— con validación de campo.

Ninguna de las dos sustituye a la otra. Nota de procedencia: en la referencia
**no existe** un ``res_config_settings.py``; este archivo es propio de este
árbol. Movido state-only desde el addon no-Odoo ``settings_app``; la tabla
física ``settings_sitesettings`` no cambia.

Complementa a ``SystemParameter`` (``ir_config_parameter.py``, config L2
key/value) — ``SiteSettings`` es el registro tipado con validación de campo.
"""
import logging
from decimal import Decimal
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.db import models

from .timestamped_mixin import TimeStampedModel

logger = logging.getLogger(__name__)


class SiteSettings(TimeStampedModel):
    """Configuración singleton del sitio. UC-CFG-03.

    DEC-DOC-005: identificadores en inglés.
    Contrato: FR-CFG-03.01 (parámetros globales) y FR-CFG-03.02 (validación).
    """
    # — Identidad del sitio —
    site_name = models.CharField(max_length=100, default='PracticaYoruba')
    # H-API-PAY10-01: UC-PAY-10 AC-05 asume un logotipo del sitio para el
    # recibo PDF. El helper de PDF (addons.payment.pdf_receipt) ya resuelve el
    # logo por path y degrada a "sin logo" si está vacío; este campo le da la
    # fuente. Mismo patrón de ImageField local que catalogue/reviews.
    logo = models.ImageField(
        upload_to='settings/logo/',
        null=True, blank=True,
        verbose_name='Logotipo',
        help_text='Logotipo del sitio para el recibo PDF (UC-PAY-10). PNG recomendado.',
    )

    # — Impuestos y umbrales —
    iva_rate = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal('0.16'),
        validators=[
            MinValueValidator(Decimal('0')),
            MaxValueValidator(Decimal('1')),
        ],
        help_text='Tasa de IVA expresada como fracción decimal entre 0 y 1 (ej. 0.16 = 16%).',
    )
    currency = models.CharField(
        max_length=3,
        default='MXN',
        validators=[
            RegexValidator(
                regex=r'^[A-Z]{3}$',
                message='Currency must be a 3-letter ISO 4217 code (uppercase).',
            ),
        ],
        help_text='Código ISO 4217 de la moneda (3 letras mayúsculas).',
    )

    # UC-ORD-10 — timeout de pago para alertas del dashboard (H-ADM-004)
    payment_timeout_minutes = models.PositiveIntegerField(
        default=30,
        help_text='Minutos hasta que una orden PENDING se cancela por timeout (UC-SYS-01).'
    )
    # UC-CFG-03 — timeout para abandono de carrito / orden
    order_timeout_minutes = models.PositiveIntegerField(
        default=30,
        validators=[MinValueValidator(1)],
        help_text='Minutos antes de que una orden sin pagar expire (FR-CFG-03.01).',
    )
    # UC-RTN-01 — ventana máxima de devolución
    max_return_days = models.PositiveIntegerField(
        default=30,
        validators=[MinValueValidator(1)],
        help_text='Días máximos para solicitar una devolución.',
    )

    min_stock_threshold = models.PositiveIntegerField(default=5)
    free_shipping_threshold = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('500.00'),
        validators=[MinValueValidator(Decimal('0'))],
    )

    # — Programa de referidos (UC-PRO-05) —
    referral_active = models.BooleanField(
        default=False,
        help_text='Si el programa de referidos esta activo (UC-PRO-05 PRE-02).',
    )
    referral_welcome_discount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('50.00'),
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text='Descuento fijo del voucher de bienvenida emitido al nuevo '
                  'comprador que canjea un codigo referral (UC-PRO-05 Subflujo B).',
    )
    referral_reward_discount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('50.00'),
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text='Descuento fijo del voucher de recompensa emitido al referidor '
                  'cuando el referido completa su primera compra (UC-PRO-05 Subflujo C).',
    )

    # — Contacto (UC-CFG-05) —
    support_email = models.EmailField(max_length=254, blank=True, default='')
    phone         = models.CharField(max_length=30, blank=True, default='')
    address       = models.TextField(blank=True, default='')
    social_links  = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table     = 'settings_sitesettings'
        verbose_name = 'Configuración del sitio'

    def __str__(self):
        return f'SiteSettings({self.site_name})'

    def clean(self):
        """Singleton: solo se permite un registro (pk=1)."""
        super().clean()
        if self.pk is None and SiteSettings.objects.exists():
            raise ValidationError('SiteSettings is a singleton; only one record is allowed.')

    # H-CICLO25-02: clave y TTL de la caché del singleton.
    # Cualquier llamada a get_current() reutiliza el valor cacheado en lugar
    # de ejecutar SELECT cada vez.  save() invalida la clave para que un cambio
    # del admin en producción sea visible en la siguiente petición (no requiere
    # reinicio del proceso WSGI).
    _CACHE_KEY = 'settings_app:site_settings:singleton'
    _CACHE_TTL = 300  # 5 minutos

    def save(self, *args, **kwargs):
        # Fijar pk=1 para reforzar el singleton a nivel de almacenamiento.
        if self.pk is None and SiteSettings.objects.exists():
            raise ValidationError('SiteSettings is a singleton; only one record is allowed.')
        if self.pk is None:
            self.pk = 1
        super().save(*args, **kwargs)
        # H-CICLO25-02: invalidar la caché tras cada save() para que los
        # cambios del admin se reflejen de inmediato sin reiniciar WSGI.
        cache.delete(self._CACHE_KEY)

    @classmethod
    def get_or_create_defaults(cls) -> 'SiteSettings':
        """Devuelve el registro singleton, creándolo con defaults si no existe."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @classmethod
    def get_current(cls) -> 'SiteSettings':
        """
        Alias retrocompatible — usar get_or_create_defaults en código nuevo.

        H-CICLO25-02: consulta la caché (DatabaseCache) antes de ir a la BD.
        TTL = 5 min. La caché se invalida en save() para que los cambios del
        admin sean efectivos sin reiniciar el proceso WSGI.
        """
        obj = cache.get(cls._CACHE_KEY)
        if obj is None:
            obj = cls.get_or_create_defaults()
            cache.set(cls._CACHE_KEY, obj, cls._CACHE_TTL)
        return obj
