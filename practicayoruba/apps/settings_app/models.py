"""
Models — apps.settings_app

Sprints 1, 8, 10. Refactorizado en sprint de infraestructura: herencia-modelos-django
  SiteSettings      → TimeStampedModel (migración 0005: ADD created_at)
  PaymentGateway    → TimeStampedModel (migración 0005: ADD created_at)
  ShippingMethod    → TimeStampedModel (migración 0005: ADD created_at)
  StaticPage        → TimeStampedModel (migración 0005: ADD created_at)
  StaticPageVersion → TimeStampedModel (migración 0005: ADD updated_at)

H-INH-004: estos 4 modelos solo tenían updated_at — se agrega created_at.
"""
from decimal import Decimal
from django.conf import settings
from django.db import models
from cryptography.fernet import Fernet

from apps.core.models import TimeStampedModel


class SiteSettings(TimeStampedModel):
    """Configuración singleton del sitio. UC-CFG-03."""
    # — Impuestos y umbrales —
    iva_rate               = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal('0.16'))
    min_stock_threshold    = models.PositiveIntegerField(default=5)
    free_shipping_threshold = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    # — Contacto (UC-CFG-05) —
    support_email = models.EmailField(max_length=254, blank=True, default='')
    phone         = models.CharField(max_length=30, blank=True, default='')
    address       = models.TextField(blank=True, default='')
    social_links  = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table     = 'settings_sitesettings'
        verbose_name = 'Configuración del sitio'

    def __str__(self):
        return 'SiteSettings'

    @classmethod
    def get_current(cls) -> 'SiteSettings':
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class PaymentGateway(TimeStampedModel):
    """Pasarela de pago configurada. UC-CFG-01."""
    GATEWAY_TEST     = 'TEST'
    GATEWAY_MERCADOPAGO = 'MERCADOPAGO'
    GATEWAY_PAYPAL   = 'PAYPAL'
    GATEWAYS = [
        (GATEWAY_TEST,        'Test (sandbox)'),
        (GATEWAY_MERCADOPAGO, 'MercadoPago'),
        (GATEWAY_PAYPAL,      'PayPal'),
    ]

    name        = models.CharField(max_length=50)
    gateway     = models.CharField(max_length=20, choices=GATEWAYS, unique=True)
    is_active   = models.BooleanField(default=False)
    credentials = models.BinaryField(
        help_text='Credenciales cifradas con Fernet (apps.settings_app.models._fernet_key)')
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table     = 'settings_payment_gateway'
        verbose_name = 'Pasarela de pago'

    def __str__(self):
        return f'{self.gateway} ({"activo" if self.is_active else "inactivo"})'

    @staticmethod
    def _fernet_key() -> bytes:
        import hashlib, base64
        raw = settings.SECRET_KEY.encode()
        digest = hashlib.sha256(raw).digest()
        return base64.urlsafe_b64encode(digest)

    def set_credentials(self, data: dict) -> None:
        import json
        f = Fernet(self._fernet_key())
        self.credentials = f.encrypt(json.dumps(data).encode())

    def get_credentials(self) -> dict:
        import json
        f = Fernet(self._fernet_key())
        return json.loads(f.decrypt(bytes(self.credentials)).decode())


class ShippingMethod(TimeStampedModel):
    """Método de envío disponible. UC-CFG-02."""
    name           = models.CharField(max_length=100)
    cost           = models.DecimalField(max_digits=10, decimal_places=2)
    estimated_days = models.PositiveSmallIntegerField()
    is_active      = models.BooleanField(default=True, db_index=True)
    free_threshold = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    zones          = models.JSONField(default=list, blank=True)

    class Meta:
        db_table     = 'settings_shipping_method'
        ordering     = ['cost', 'name']
        verbose_name = 'Método de envío'

    def __str__(self):
        return f'{self.name} (${self.cost})'


class StaticPage(TimeStampedModel):
    """Página estática del sitio. UC-CFG-04."""
    PAGE_ABOUT   = 'about'
    PAGE_TERMS   = 'terms'
    PAGE_PRIVACY = 'privacy'
    PAGE_RETURNS = 'returns'
    PAGE_FAQ     = 'faq'
    PAGE_CHOICES = [
        (PAGE_ABOUT,   'Acerca de nosotros'),
        (PAGE_TERMS,   'Términos y condiciones'),
        (PAGE_PRIVACY, 'Política de privacidad'),
        (PAGE_RETURNS, 'Política de devoluciones'),
        (PAGE_FAQ,     'Preguntas frecuentes'),
    ]

    slug  = models.SlugField(max_length=20, unique=True, choices=PAGE_CHOICES)
    title = models.CharField(max_length=200)

    class Meta:
        db_table     = 'settings_static_page'
        verbose_name = 'Página estática'

    def __str__(self):
        return self.get_slug_display()

    @property
    def current_version(self):
        return self.versions.filter(status='PUBLISHED').order_by('-version').first()


class StaticPageVersion(TimeStampedModel):
    """
    Versión de una página estática. UC-CFG-04 (FR-CFG-04.02).
    updated_at registra cuándo se modificó el estado (DRAFT→PUBLISHED→ARCHIVED).
    """
    STATUS_DRAFT     = 'DRAFT'
    STATUS_PUBLISHED = 'PUBLISHED'
    STATUS_ARCHIVED  = 'ARCHIVED'
    STATUS_CHOICES   = [
        (STATUS_DRAFT,     'Borrador'),
        (STATUS_PUBLISHED, 'Publicado'),
        (STATUS_ARCHIVED,  'Archivado'),
    ]

    page       = models.ForeignKey(StaticPage, on_delete=models.CASCADE, related_name='versions')
    version    = models.PositiveIntegerField()
    content    = models.TextField()
    status     = models.CharField(max_length=12, choices=STATUS_CHOICES,
                                  default=STATUS_DRAFT, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL,
                                   related_name='static_page_versions')
    publish_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table        = 'settings_static_page_version'
        unique_together = [('page', 'version')]
        ordering        = ['-version']
        verbose_name    = 'Versión de página estática'

    def __str__(self):
        return f'{self.page.slug} v{self.version} ({self.status})'
