"""
Models — apps.addons.search_history (UC-SRCH-03 — append-only).

A separate SearchEntry table from catalogue.SearchHistory to capture
analytic information (normalized_query, results_count) without
touching the existing catalogue model. Append-only — NO heredamos
SoftDeleteModel (DEC-DOC-007 audit exception).
"""
from django.conf import settings
from django.db import models
from apps.core.models import TimeStampedModel



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
