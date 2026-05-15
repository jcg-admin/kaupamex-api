"""
SiteSettings — UC-CFG-03
Singleton de configuración global del sistema.
"""
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class SiteSettings(models.Model):
    site_name = models.CharField(max_length=100, default='PracticaYoruba')
    iva_rate = models.DecimalField(
        max_digits=5, decimal_places=4,
        default=Decimal('0.16'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('1.00'))],
    )
    currency = models.CharField(max_length=3, default='MXN')
    order_timeout_minutes = models.PositiveIntegerField(
        default=30, validators=[MinValueValidator(1)]
    )
    max_return_days = models.PositiveIntegerField(
        default=30, validators=[MinValueValidator(1)]
    )
    free_shipping_threshold = models.DecimalField(
        max_digits=10, decimal_places=2,
        default=Decimal('500.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    min_stock_threshold = models.PositiveIntegerField(
        default=5,
        validators=[MinValueValidator(1)],
        help_text='Umbral minimo de stock que activa alertas de inventario (FR-INV-01.02).',
        verbose_name='Umbral minimo de stock',
    )
    avatar_max_size_mb = models.PositiveIntegerField(
        default=5,
        validators=[MinValueValidator(1)],
        help_text='Tamaño maximo permitido para avatares, en MB (FR-AUTH-06.04).',
        verbose_name='Tamaño maximo avatar (MB)',
    )
    max_addresses_per_user = models.PositiveIntegerField(
        default=5,
        validators=[MinValueValidator(1)],
        help_text='Numero maximo de direcciones de envio por comprador (FR-AUTH-07.02).',
        verbose_name='Maximo de direcciones por usuario',
    )
    # Datos de contacto del negocio (UC-CFG-05)
    support_email = models.EmailField(max_length=254, blank=True, default='',
                        verbose_name='Email de soporte',
                        help_text='Visible en footer y emails transaccionales.')
    phone         = models.CharField(max_length=30, blank=True, default='',
                        verbose_name='Telefono de contacto')
    address       = models.TextField(blank=True, default='',
                        verbose_name='Direccion fisica')
    social_links  = models.JSONField(default=dict, blank=True,
                        verbose_name='Redes sociales',
                        help_text='Dict de plataforma→URL. Ej: {"instagram":"https://..."}.')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'settings_sitesettings'
        verbose_name = 'Configuracion del sitio'

    def __str__(self):
        return f'SiteSettings — {self.site_name} (IVA {float(self.iva_rate):.0%})'

    def clean(self):
        if self.currency and len(self.currency) != 3:
            raise ValidationError({'currency': 'Debe tener 3 caracteres.'})
        if self.iva_rate is not None:
            if self.iva_rate < Decimal('0.00') or self.iva_rate > Decimal('1.00'):
                raise ValidationError({'iva_rate': 'Debe estar entre 0.00 y 1.00.'})
        if self.free_shipping_threshold is not None and self.free_shipping_threshold < 0:
            raise ValidationError({'free_shipping_threshold': 'No puede ser negativo.'})
        if self.order_timeout_minutes is not None and self.order_timeout_minutes < 1:
            raise ValidationError({'order_timeout_minutes': 'Debe ser >= 1 minuto.'})

    def save(self, *args, **kwargs):
        if not self.pk and SiteSettings.objects.exists():
            raise ValidationError('SiteSettings es un singleton.')
        super().save(*args, **kwargs)

    @classmethod
    def get_or_create_defaults(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @classmethod
    def get_current(cls):
        return cls.get_or_create_defaults()


# =============================================================================
# Sprint 8 — UC-CFG-01 y UC-CFG-02
# =============================================================================

def _fernet_key() -> bytes:
    """
    Deriva una clave Fernet de 32 bytes desde SECRET_KEY.
    Usa los primeros 32 bytes del SHA-256 de la clave, codificados en base64 URL-safe.
    """
    import hashlib, base64
    from django.conf import settings
    raw = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return base64.urlsafe_b64encode(raw)


class PaymentGateway(models.Model):
    """
    Configuracion de un gateway de pago. UC-CFG-01.
    Las credenciales se almacenan cifradas con Fernet (AES-128-CBC + HMAC).
    Un registro por provider (unique). No se crea automaticamente —
    el admin configura cada gateway desde el panel.
    """
    PROVIDER_MP     = 'mercado_pago'
    PROVIDER_PAYPAL = 'paypal'
    PROVIDERS = [
        (PROVIDER_MP,     'Mercado Pago'),
        (PROVIDER_PAYPAL, 'PayPal'),
    ]

    provider        = models.CharField(
        max_length=20, unique=True, choices=PROVIDERS,
        verbose_name='Proveedor de pago',
    )
    is_active       = models.BooleanField(default=False, db_index=True)
    credentials_enc = models.TextField(blank=True, default='',
                          verbose_name='Credenciales cifradas (Fernet JSON)')
    verified_at     = models.DateTimeField(null=True, blank=True,
                          verbose_name='Última verificación de conectividad')
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        db_table   = 'settings_payment_gateway'
        verbose_name = 'Gateway de pago'

    def __str__(self):
        return f'{self.get_provider_display()} ({"activo" if self.is_active else "inactivo"})'

    def set_credentials(self, credentials: dict) -> None:
        """Cifra y almacena el dict de credenciales."""
        import json
        from cryptography.fernet import Fernet
        f = Fernet(_fernet_key())
        raw = json.dumps(credentials).encode()
        self.credentials_enc = f.encrypt(raw).decode()

    def get_credentials(self) -> dict:
        """Descifra y retorna el dict de credenciales. Retorna {} si no hay."""
        if not self.credentials_enc:
            return {}
        import json
        from cryptography.fernet import Fernet, InvalidToken
        try:
            f = Fernet(_fernet_key())
            raw = f.decrypt(self.credentials_enc.encode())
            return json.loads(raw)
        except (InvalidToken, Exception):
            return {}

    def get_masked_credentials(self) -> dict:
        """Retorna las credenciales con los valores enmascarados (últimos 4 chars)."""
        creds = self.get_credentials()
        masked = {}
        for key, val in creds.items():
            s = str(val)
            masked[key] = '*' * max(0, len(s) - 4) + s[-4:] if len(s) > 4 else '****'
        return masked


class ShippingMethod(models.Model):
    """
    Metodo de envio configurable. UC-CFG-02.
    El campo 'zones' es una lista de codigos ISO de estado/region.
    Lista vacia = aplica a todo el territorio.
    """
    name           = models.CharField(max_length=100, verbose_name='Nombre')
    description    = models.TextField(blank=True, default='',
                         verbose_name='Descripcion')
    cost           = models.DecimalField(
        max_digits=8, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Costo de envio',
    )
    estimated_days = models.PositiveSmallIntegerField(
        verbose_name='Dias habiles estimados',
        validators=[MinValueValidator(1)],
    )
    is_active      = models.BooleanField(default=True, db_index=True)
    free_threshold = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True,
        verbose_name='Monto minimo para envio gratis',
        help_text='Si el subtotal del carrito supera este monto, el costo es 0.',
    )
    zones          = models.JSONField(
        default=list, blank=True,
        verbose_name='Zonas geograficas',
        help_text='Lista de codigos ISO de estado. Vacio = todo el territorio.',
    )
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        db_table     = 'settings_shipping_method'
        ordering     = ['cost', 'name']
        verbose_name = 'Metodo de envio'

    def __str__(self):
        return f'{self.name} — ${self.cost} ({self.estimated_days}d)'


# =============================================================================
# Sprint 10 — UC-CFG-04: Contenido estático con versionado
# =============================================================================

class StaticPage(models.Model):
    """
    Página estática del sitio. UC-CFG-04.
    Cada página tiene un historial de versiones numeradas.
    """
    PAGE_ABOUT    = 'about'
    PAGE_TERMS    = 'terms'
    PAGE_PRIVACY  = 'privacy'
    PAGE_RETURNS  = 'returns'
    PAGE_FAQ      = 'faq'
    PAGE_CHOICES  = [
        (PAGE_ABOUT,   'Acerca de nosotros'),
        (PAGE_TERMS,   'Términos y condiciones'),
        (PAGE_PRIVACY, 'Política de privacidad'),
        (PAGE_RETURNS, 'Política de devoluciones'),
        (PAGE_FAQ,     'Preguntas frecuentes'),
    ]

    slug       = models.SlugField(max_length=20, unique=True, choices=PAGE_CHOICES)
    title      = models.CharField(max_length=200)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table     = 'settings_static_page'
        verbose_name = 'Página estática'

    def __str__(self):
        return self.get_slug_display()

    @property
    def current_version(self):
        """Retorna la version PUBLISHED activa, o None."""
        return self.versions.filter(status='PUBLISHED').order_by('-version').first()


class StaticPageVersion(models.Model):
    """
    Version de una página estática. UC-CFG-04 (FR-CFG-04.02).
    Solo una version por página puede estar en estado PUBLISHED.
    """
    STATUS_DRAFT     = 'DRAFT'
    STATUS_PUBLISHED = 'PUBLISHED'
    STATUS_ARCHIVED  = 'ARCHIVED'
    STATUS_CHOICES   = [
        (STATUS_DRAFT,     'Borrador'),
        (STATUS_PUBLISHED, 'Publicado'),
        (STATUS_ARCHIVED,  'Archivado'),
    ]

    page       = models.ForeignKey(
        StaticPage, on_delete=models.CASCADE,
        related_name='versions',
    )
    version    = models.PositiveIntegerField(verbose_name='Número de versión')
    content    = models.TextField(verbose_name='Contenido HTML')
    status     = models.CharField(
        max_length=12, choices=STATUS_CHOICES,
        default=STATUS_DRAFT, db_index=True,
    )
    created_by = models.ForeignKey(
        'users.User', null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='static_page_versions',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    publish_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Publicar en fecha futura',
        help_text='Si está en blanco, la publicación es inmediata. '
                  'El cron UC-SYS-04 activará las programadas (Sprint 33).',
    )

    class Meta:
        db_table        = 'settings_static_page_version'
        unique_together = [('page', 'version')]
        ordering        = ['-version']
        verbose_name    = 'Versión de página estática'

    def __str__(self):
        return f'{self.page.slug} v{self.version} ({self.status})'
