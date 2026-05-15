"""
Models — apps.catalogue

Sprint 4 — UC-CAT-01: Ver Catálogo de Productos
Sprint 5 — UC-CAT-02, UC-CAT-03, UC-SRCH-01
Sprint 6 — UC-SRCH-03 (SearchHistory), UC-CAT-04, UC-CAT-05, UC-CAT-06
"""
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator


class Category(models.Model):
    name        = models.CharField(max_length=100, unique=True)
    slug        = models.SlugField(max_length=120, unique=True, db_index=True)
    description = models.TextField(blank=True, default='')
    parent      = models.ForeignKey(
        'self', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='children',
    )
    is_active   = models.BooleanField(default=True)

    class Meta:
        db_table    = 'catalogue_category'
        verbose_name_plural = 'categories'
        ordering    = ['name']

    def __str__(self):
        return self.name

    def get_descendants_pks(self):
        """
        Retorna un set de PKs que incluye esta categoría y todos sus
        descendientes activos. Usado por UC-CAT-04 (FR-CAT-04.02).
        Complejidad O(n) con n = total de categorías activas.
        """
        pks = {self.pk}
        queue = list(
            Category.objects.filter(parent=self, is_active=True)
            .values_list('pk', flat=True)
        )
        while queue:
            pk = queue.pop()
            pks.add(pk)
            children_pks = list(
                Category.objects.filter(parent_id=pk, is_active=True)
                .values_list('pk', flat=True)
            )
            queue.extend(children_pks)
        return pks

    def would_create_cycle(self, proposed_parent):
        """
        Detecta si asignar proposed_parent como padre de esta categoría
        crearía un ciclo en la jerarquía. FR-CAT-06.02.

        Retorna True si habría ciclo, False si la operación es segura.
        """
        if proposed_parent is None:
            return False
        if proposed_parent.pk == self.pk:
            return True
        # Subir por la cadena de ancestros del propuesto
        current = proposed_parent
        while current.parent is not None:
            if current.parent.pk == self.pk:
                return True
            current = current.parent
        return False


class Product(models.Model):
    name         = models.CharField(max_length=200)
    slug         = models.SlugField(max_length=220, unique=True, db_index=True)
    sku          = models.CharField(max_length=50, unique=True)
    short_description = models.CharField(max_length=500, blank=True, default='')
    description  = models.TextField(blank=True, default='')
    category     = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name='products',
    )
    price        = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    stock        = models.PositiveIntegerField(default=0)
    is_featured  = models.BooleanField(default=False, db_index=True)
    is_active    = models.BooleanField(default=True, db_index=True)
    is_published = models.BooleanField(default=False, db_index=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'catalogue_product'
        ordering = ['-created_at']

    @property
    def availability(self):
        if self.stock > 0:
            return 'IN_STOCK'
        return 'OUT_OF_STOCK'

    def __str__(self):
        return self.name


class SearchHistory(models.Model):
    """
    Historial de búsquedas de un comprador autenticado. UC-SRCH-03.

    Invariantes:
    - Máximo 20 registros por usuario (los más recientes).
    - Unicidad (user, term): si el mismo término se busca de nuevo,
      solo se actualiza searched_at (upsert).
    - El término se guarda normalizado (strip + lowercase + colapso de espacios).
    """
    user        = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='search_history',
    )
    term        = models.CharField(max_length=100, db_index=True)
    searched_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table       = 'catalogue_search_history'
        unique_together = [('user', 'term')]
        ordering        = ['-searched_at']
        verbose_name    = 'Historial de búsqueda'

    def __str__(self):
        return f'{self.user.username} → "{self.term}"'

    @classmethod
    def record(cls, user, term: str) -> None:
        """
        Registra o actualiza el término para el usuario.
        Aplica el trim a 20 entradas más recientes. Idempotente.
        FR-SRCH-03.01.
        """
        # Upsert: update_or_create por (user, term)
        cls.objects.update_or_create(
            user=user, term=term,
            defaults={},   # searched_at se actualiza via auto_now=True al save()
        )
        # Trim: eliminar entradas más antiguas si supera el límite
        max_entries = 20
        total = cls.objects.filter(user=user).count()
        if total > max_entries:
            # IDs de los más antiguos a eliminar
            oldest_ids = list(
                cls.objects.filter(user=user)
                .order_by('searched_at')
                .values_list('pk', flat=True)[:total - max_entries]
            )
            cls.objects.filter(pk__in=oldest_ids).delete()
