"""
Models — apps.static_content (UC-CFG-04).

StaticContent: páginas de contenido estático (privacy-policy, terms,
about-us, etc.) editables por administradores con version history.

StaticContentVersion: append-only audit log per DEC-DOC-007 exception.
"""
from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


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
        db_table        = 'static_content_version'
        unique_together = [('content', 'version')]
        ordering        = ['-version']
        verbose_name    = 'Version de contenido'
