"""
Models — apps.inventory
Sprint 10 — UC-INV-01 (Ver Stock), UC-INV-02 (Decrementar Stock)
"""
from django.conf import settings
from django.db import models


class StockMovement(models.Model):
    """
    Registro de cada cambio de stock. UC-INV-02, UC-INV-03, UC-INV-04.
    delta negativo = decremento (SALE), positivo = incremento (CANCELLATION/ADJUSTMENT).
    """
    TYPE_SALE         = 'SALE'
    TYPE_CANCELLATION = 'CANCELLATION'
    TYPE_ADJUSTMENT   = 'ADJUSTMENT'
    TYPE_IMPORT       = 'IMPORT'
    TYPES = [
        (TYPE_SALE,         'Venta'),
        (TYPE_CANCELLATION, 'Cancelacion'),
        (TYPE_ADJUSTMENT,   'Ajuste manual'),
        (TYPE_IMPORT,       'Importacion CSV'),
    ]

    variant       = models.ForeignKey(
        'chartsize.ProductVariant', null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='stock_movements',
        help_text='Variante afectada. Null si el producto no tiene variantes.',
    )
    product       = models.ForeignKey(
        'catalogue.Product', on_delete=models.CASCADE,
        related_name='stock_movements',
    )
    delta         = models.IntegerField(
        verbose_name='Delta de stock',
        help_text='Negativo para decrementos, positivo para incrementos.',
    )
    stock_after   = models.PositiveIntegerField(verbose_name='Stock tras el movimiento')
    movement_type = models.CharField(max_length=20, choices=TYPES, db_index=True)
    reference     = models.CharField(
        max_length=50, blank=True, default='',
        verbose_name='Referencia',
        help_text='Numero de orden o identificador externo.',
    )
    notes         = models.TextField(blank=True, default='')
    created_by    = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='stock_movements',
    )
    created_at    = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table     = 'inventory_stock_movement'
        ordering     = ['-created_at']
        verbose_name = 'Movimiento de stock'

    def __str__(self):
        return f'{self.movement_type} {self.delta:+d} → {self.stock_after} ({self.product.sku})'


class StockAlert(models.Model):
    """
    Alerta de stock bajo o agotado. UC-INV-02 (FR-INV-02.02).
    Se crea cuando el stock cae por debajo de SiteSettings.min_stock_threshold.
    Deduplicacion: no se crea si ya existe una alerta sin resolver en las ultimas 24h.
    """
    variant       = models.ForeignKey(
        'chartsize.ProductVariant', null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='stock_alerts',
    )
    product       = models.ForeignKey(
        'catalogue.Product', on_delete=models.CASCADE,
        related_name='stock_alerts',
    )
    stock_at_alert = models.PositiveIntegerField(verbose_name='Stock al momento de la alerta')
    resolved       = models.BooleanField(default=False, db_index=True)
    resolved_at    = models.DateTimeField(null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table     = 'inventory_stock_alert'
        ordering     = ['-created_at']
        verbose_name = 'Alerta de stock'

    def __str__(self):
        return f'Alerta {self.product.sku} stock={self.stock_at_alert}'
