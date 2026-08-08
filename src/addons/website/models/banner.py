"""Banner promocional.

**Sin análogo en la referencia**: en Odoo los banners son *snippets* del
editor de sitios (bloques QWeb), no un modelo de datos. Aquí es un modelo
propio porque el cliente es un SPA React sin editor de bloques.
"""
from django.conf import settings
from django.db import models

from addons.base.models import TimeStampedModel


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
