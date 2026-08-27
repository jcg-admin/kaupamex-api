"""Contenido estático con historial (UC-CFG-04) — interinato conservado.

En la referencia el equivalente es ``website.page``, que **delega** en
``ir.ui.view`` (``_inherits``) y saca de ahí su versionado — **#104 ya lo
portó** (``website_page.py``; ``ir.ui.view`` vive en ``base`` desde #544).

**Decisión de #104: este par se CONSERVA, absorbido en papel pero no en
datos** — misma decisión y mismas razones que ``static_page.py`` (flujo
editorial con historial sin hogar en ``website.page`` mientras el COW de la
vista no esté portado; consumidores REST vivos en
``controllers/static_content*.py`` y sus tests de integración). Ninguna
tabla se borra ni migra; la migración de contenido y endpoints va en la
tarea **#560**.
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
