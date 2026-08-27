"""Página estática de settings con historial — interinato conservado por #104.

Duplica el propósito de ``static_content.py`` — ambos pares modelan "página
con versionado". La referencia tiene **un** modelo (``website.page``), que
**#104 ya portó** (``website_page.py``, delegando en ``ir.ui.view``).

**Decisión de #104: este par se CONSERVA, absorbido en papel pero no en
datos.** Razones, medidas en el pase:

- El flujo editorial DRAFT→PUBLISHED→ARCHIVED con historial
  (``StaticPageVersion``) no tiene hogar en ``website.page``: allá el
  versionado sale del COW de ``ir.ui.view``, que no está portado.
- Los consumidores REST (``controllers/main.py``, serializers,
  ``authz_catalog`` y los tests de integración) sirven este par; migrar su
  contrato público excede el pase y es la tarea **#560**.

Ninguna tabla se borra ni migra: cero pérdida de datos. Los consumidores
internos de ``Website`` (``get_unique_path``, ``check_existing_page``,
``_enumerate_pages``) ya consultan ``website.page`` como primario y este par
como interinato.
"""
from django.conf import settings
from django.db import models

from addons.base.models import TimeStampedModel
from addons.website.models.mixins import WebsiteSearchableMixin
from orm.domains import Domain


class StaticPage(WebsiteSearchableMixin, TimeStampedModel):
    """Página estática del sitio. UC-CFG-04.

    Hereda ``WebsiteSearchableMixin`` como su análogo ``website.page`` en la
    referencia (``odoo19c: website/models/website_page.py:29`` —
    ``_inherit = [... 'website.searchable.mixin']``): es el primer modelo
    buscable desde ``Website._search_with_fuzzy``. #104 portó
    ``website.page``; este modelo queda como interinato conservado (ver el
    docstring del módulo).
    """
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

    @property
    def url(self):
        """URL pública de la página — ≙ el campo ``url`` de ``website.page``.

        Allá es una columna propia porque cualquier página puede vivir en
        cualquier ruta; aquí las páginas estáticas se sirven bajo un prefijo
        fijo (``PublicStaticPageView``, ``controllers/main.py``), así que la
        URL se deriva del ``slug`` en vez de almacenarse.
        """
        return f'/pages/{self.slug}'

    @classmethod
    def _search_get_detail(cls, website, order, options):
        """≙ ``website.page._search_get_detail`` (``odoo19c: website_page.py:202``).

        La receta de búsqueda de las páginas. Divergencias declaradas contra
        la fuente, cada una con su porqué:

        - ``base_domain`` restringe a páginas **con versión publicada** — el
          análogo de su ``website_published = True``; aquí la publicación
          vive en ``StaticPageVersion.status``.
        - Sin el recorte por sitio (``website.website_domain()``): este
          modelo es el interinato conservado por #104 y no declara FK a
          ``website`` — el recorte por sitio vive en la receta de
          ``website.page`` (``WebsitePage._search_get_detail``).
        - Sin los escalones de visibilidad por grupo/contraseña: son del
          mixin ``website.page_options.mixin``, sin portar (arista declarada
          en ``website_page.py``).
        - ``requires_sudo`` se conserva en ``True`` — mismo motivo que la
          fuente comenta (la lectura pública pasa por encima de las record
          rules) — y ``model`` lleva la clase (ver el mixin).
        - La rama ``displayDescription`` (``arch_db``) no aplica: el HTML
          vive en la versión, no en la página; la receta de ``website.page``
          sí la trae.
        """
        return {
            'model': cls,
            'base_domain': [Domain('versions.status', '=', 'PUBLISHED')],
            'requires_sudo': True,
            'search_fields': ['title', 'slug'],
            'fetch_fields': ['id', 'title', 'url'],
            'mapping': {
                'name': {'name': 'title', 'type': 'text', 'match': True},
                'website_url': {'name': 'url', 'type': 'text', 'truncate': False},
            },
            'icon': 'fa-file-o',
        }


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
