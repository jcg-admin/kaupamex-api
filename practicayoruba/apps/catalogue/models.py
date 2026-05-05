"""
Models — apps.catalogue

Sprint 4 — UC-CAT-01: Ver Catálogo de Productos
"""
from decimal import Decimal
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
    is_active    = models.BooleanField(default=True, db_index=True)
    is_published = models.BooleanField(default=False, db_index=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'catalogue_product'
        ordering = ['-created_at']
        indexes = [
            # FULLTEXT index para UC-SRCH-01 — se crea via RunSQL en la migración
        ]

    @property
    def availability(self):
        if self.stock > 0:
            return 'available'
        return 'out_of_stock'

    def __str__(self):
        return self.name
