"""Historial de búsquedas del sitio.

El pariente más cercano en la referencia es ``website.track`` (páginas
visitadas por ``website.visitor``), que registra navegación, no consultas.
No es el mismo modelo; ver ``alinear-addon-website-referencia``.
"""
from django.conf import settings
from django.db import models

from addons.base.models import TimeStampedModel


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
