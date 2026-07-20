"""
Models — addons.website (UC-CFG-04).

StaticContent: páginas de contenido estático (privacy-policy, terms,
about-us, etc.) editables por administradores con version history.

StaticContentVersion: append-only audit log per DEC-DOC-007 exception.
"""
from django.conf import settings
from django.db import models
from addons.base.models import TimeStampedModel



class StaticContent(TimeStampedModel):
    """Static content page identified by slug."""
    slug    = models.SlugField(max_length=80, unique=True)
    title   = models.CharField(max_length=200)
    body    = models.TextField()
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table     = 'static_content_page'
        ordering     = ['slug']
        verbose_name = 'Contenido estatico'

    def __str__(self):
        return f'{self.slug} (v{self.version})'


class StaticContentVersion(TimeStampedModel):
    """Append-only history of static content edits."""
    content    = models.ForeignKey(
        StaticContent, on_delete=models.CASCADE, related_name='versions',
    )
    version    = models.PositiveIntegerField()
    title      = models.CharField(max_length=200)
    body       = models.TextField()
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+',
    )

    class Meta:
        db_table     = 'static_content_version'
        constraints  = [
            models.UniqueConstraint(
                fields=['content', 'version'],
                name='unique_static_content_version',
            )
        ]
        ordering     = ['-version']
        verbose_name = 'Version de contenido'


# --- Re-alojados desde settings_app (2026-07-20): páginas estáticas + banner
# son contenido de sitio, cuyo hogar fiel Odoo es el módulo website. ---

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
        db_table     = 'settings_static_page_version'
        constraints  = [
            models.UniqueConstraint(
                fields=['page', 'version'],
                name='unique_static_page_version',
            )
        ]
        ordering     = ['-version']
        verbose_name = 'Versión de página estática'

    def __str__(self):
        return f'{self.page.slug} v{self.version} ({self.status})'


class Banner(TimeStampedModel):
    """Contenido visual gestionable de la portada (UC-CFG-06, G-CFG-01).

    Un solo modelo para el hero de portada y las franjas promocionales,
    distinguidos por ``placement`` (evita duplicar CRUD para campos idénticos).
    El storefront lee los activos por placement vía
    ``GET /api/v2/config/banners/?placement=HERO`` (público); el admin los
    gestiona (CRUD + reorder) con la capacidad ``banners.manage``.
    """

    class Placement(models.TextChoices):
        HERO        = 'HERO', 'Hero de portada'
        PROMO_STRIP = 'PROMO_STRIP', 'Franja promocional'

    image      = models.ImageField(upload_to='banners/%Y/%m/', verbose_name='Imagen')
    placement  = models.CharField(max_length=20, choices=Placement.choices,
                                  db_index=True, verbose_name='Ubicación')
    title      = models.CharField(max_length=200, blank=True, default='', verbose_name='Título')
    alt_text   = models.CharField(max_length=200, verbose_name='Texto alternativo')
    link_url   = models.URLField(blank=True, default='', verbose_name='Enlace')
    is_active  = models.BooleanField(default=True, db_index=True, verbose_name='Activo')
    order      = models.PositiveSmallIntegerField(default=0, verbose_name='Orden')

    class Meta:
        db_table     = 'settings_banner'
        ordering     = ['placement', 'order', 'id']
        verbose_name = 'Banner'
        verbose_name_plural = 'Banners'
        indexes = [models.Index(fields=['placement', 'is_active', 'order'])]

    def __str__(self):
        return f'{self.placement} #{self.order} ({self.alt_text})'


# ── Historial de búsqueda (visitor behavior — movido de addons.search_history) ──
# En Odoo el rastreo de comportamiento del visitante del storefront vive en el
# módulo ``website`` (``website.visitor``/``website.track``). ``SearchEntry`` es
# la telemetría append-only de las búsquedas por usuario (UC-SRCH-03), su hogar
# fiel es ``website``. Append-only: NO hereda SoftDeleteModel (excepción de
# auditoría DEC-DOC-007).
class SearchEntry(TimeStampedModel):
    """Append-only search history entry."""
    user           = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='search_entries',
    )
    query          = models.CharField(max_length=200)
    normalized_query = models.CharField(max_length=200, db_index=True)
    results_count  = models.PositiveIntegerField(default=0)

    class Meta:
        db_table     = 'search_history_entry'
        ordering     = ['-created_at']
        verbose_name = 'Entrada de historial de busqueda'

    def __str__(self):
        return f'{self.user.email}: {self.normalized_query!r}'
