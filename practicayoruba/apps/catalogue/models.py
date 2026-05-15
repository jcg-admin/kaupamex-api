"""
Models — apps.catalogue

Sprints 4-9. Refactorizado en sprint de infraestructura: herencia-modelos-django
  Product       → TimeStampedModel (refactor puro, sin migración)
  Category      → TimeStampedModel (migración 0006: ADD created_at + updated_at)
  SearchHistory → TimeStampedModel (migración 0006: RENAME searched_at→updated_at + ADD created_at)
                  API mantiene el campo como 'searched_at' via source='updated_at' en serializer.
  ProductImage  → TimeStampedModel (migración 0006: ADD created_at + updated_at)
"""
import threading
from django.conf import settings
from django.db import models
from django.contrib.postgres.search import SearchVectorField
from django.contrib.postgres.indexes import GinIndex

from apps.core.models import TimeStampedModel


class Category(TimeStampedModel):
    """Categoría del catálogo con árbol jerárquico. UC-CAT-04/05/06."""
    name        = models.CharField(max_length=100, unique=True)
    slug        = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True, default='')
    parent      = models.ForeignKey(
        'self', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='children',
    )
    image       = models.ImageField(upload_to='categories/', null=True, blank=True)
    is_active   = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table     = 'catalogue_category'
        ordering     = ['name']
        verbose_name = 'Categoría'

    def __str__(self):
        return self.name

    def get_descendants_ids(self):
        ids = []
        queue = list(self.children.filter(is_active=True).values_list('pk', flat=True))
        while queue:
            child_id = queue.pop()
            ids.append(child_id)
            queue.extend(
                Category.objects.filter(parent_id=child_id, is_active=True)
                .values_list('pk', flat=True)
            )
        return ids


class Product(TimeStampedModel):
    """Producto del catálogo. UC-CAT-01/02/09/10/11/12."""
    name              = models.CharField(max_length=200)
    slug              = models.SlugField(max_length=220, unique=True)
    sku               = models.CharField(max_length=50, unique=True, db_index=True)
    description       = models.TextField(blank=True, default='')
    short_description = models.TextField(max_length=300, blank=True, default='')
    category          = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name='products',
    )
    price             = models.DecimalField(max_digits=10, decimal_places=2)
    stock             = models.IntegerField(default=0)
    is_active         = models.BooleanField(default=True, db_index=True)
    is_published      = models.BooleanField(default=False, db_index=True)
    search_vector     = SearchVectorField(null=True, blank=True)

    class Meta:
        db_table     = 'catalogue_product'
        ordering     = ['-created_at']
        indexes      = [GinIndex(fields=['search_vector'], name='product_search_gin')]
        verbose_name = 'Producto'

    def __str__(self):
        return self.name


class SearchHistory(TimeStampedModel):
    """
    Historial de búsquedas del usuario. UC-SRCH-03.
    Upsert por (user, term): cada búsqueda actualiza updated_at.

    H-INH-002: el campo fue renombrado de searched_at a updated_at
    internamente. La API mantiene el nombre 'searched_at' via
    source='updated_at' en SearchHistorySerializer (backward compatible).
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='search_history',
    )
    term = models.CharField(max_length=200)

    class Meta:
        db_table        = 'catalogue_search_history'
        unique_together = [('user', 'term')]
        ordering        = ['-updated_at']
        verbose_name    = 'Historial de búsqueda'

    def __str__(self):
        return f'{self.user.username}: "{self.term}"'

    @classmethod
    def record(cls, user, term: str) -> None:
        """
        Crea o actualiza el registro de búsqueda.
        Mantiene un máximo de 20 términos por usuario eliminando el más antiguo.
        """
        obj, created = cls.objects.get_or_create(
            user=user, term=term,
            defaults={},
        )
        if not created:
            # Forzar actualización de updated_at (auto_now)
            obj.save(update_fields=['updated_at'])

        def trim():
            qs = cls.objects.filter(user=user).order_by('updated_at')
            count = qs.count()
            if count > 20:
                oldest_ids = list(qs.values_list('pk', flat=True)[:count - 20])
                cls.objects.filter(pk__in=oldest_ids).delete()

        t = threading.Thread(target=trim, daemon=True)
        t.start()


class ProductImage(TimeStampedModel):
    """Imagen asociada a un producto. UC-CAT-09."""
    product  = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image    = models.ImageField(upload_to='products/images/')
    alt_text = models.CharField(max_length=200, blank=True, default='')
    order    = models.PositiveSmallIntegerField(default=0)
    is_cover = models.BooleanField(default=False)

    class Meta:
        db_table     = 'catalogue_product_image'
        ordering     = ['order', 'id']
        verbose_name = 'Imagen de producto'

    def __str__(self):
        return f'{self.product.name} — imagen {self.order}'
