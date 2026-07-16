"""\nModels — apps.modules.inventory\nSprint 10 — UC-INV-01, UC-INV-02\n"""
from django.conf import settings
from django.db import models
from apps.core.models import TimeStampedModel


class StockMovement(TimeStampedModel):
    TYPE_SALE         = 'SALE'
    TYPE_CANCELLATION = 'CANCELLATION'
    TYPE_ADJUSTMENT   = 'ADJUSTMENT'
    TYPE_IMPORT       = 'IMPORT'
    TYPE_RESTOCK      = 'RESTOCK'
    TYPES = [
        (TYPE_SALE,         'Venta'),
        (TYPE_CANCELLATION, 'Cancelacion'),
        (TYPE_ADJUSTMENT,   'Ajuste manual'),
        (TYPE_IMPORT,       'Importacion CSV'),
        (TYPE_RESTOCK,      'Entrada de stock'),
    ]

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    variant       = models.ForeignKey(
        'chartsize.ProductVariant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='stock_movements',
    )
    product       = models.ForeignKey(
        'catalogue.Product', on_delete=models.CASCADE, related_name='stock_movements',
    )
    delta         = models.IntegerField()
    stock_before  = models.IntegerField(null=True, blank=True)
    stock_after   = models.PositiveIntegerField()
    movement_type = models.CharField(max_length=20, choices=TYPES, db_index=True)
    reason        = models.CharField(max_length=50, blank=True, default='')
    reference     = models.CharField(max_length=50, blank=True, default='')
    notes         = models.TextField(blank=True, default='')
    created_by    = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='stock_movements',
    )

    class Meta:
        db_table     = 'inventory_stock_movement'
        ordering     = ['-created_at']
        verbose_name = 'Movimiento de stock'

    def __str__(self):
        return f'{self.movement_type} {self.delta:+d} → {self.stock_after} ({self.product.sku})'


class StockAlert(TimeStampedModel):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    variant        = models.ForeignKey(
        'chartsize.ProductVariant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='stock_alerts',
    )
    product        = models.ForeignKey(
        'catalogue.Product', on_delete=models.CASCADE, related_name='stock_alerts',
    )
    stock_at_alert = models.PositiveIntegerField()
    resolved       = models.BooleanField(default=False, db_index=True)
    resolved_at    = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table     = 'inventory_stock_alert'
        ordering     = ['-created_at']
        verbose_name = 'Alerta de stock'

    def __str__(self):
        return f'Alerta {self.product.sku} stock={self.stock_at_alert}'


class ImportJob(models.Model):
    STATUS_PENDING  = 'PENDING'
    STATUS_RUNNING  = 'RUNNING'
    STATUS_DONE     = 'DONE'
    STATUS_FAILED   = 'FAILED'
    STATUSES = [
        (STATUS_PENDING, 'Pendiente'),
        (STATUS_RUNNING, 'En proceso'),
        (STATUS_DONE,    'Completado'),
        (STATUS_FAILED,  'Fallido'),
    ]

    uploaded_by   = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='import_jobs',
    )
    file          = models.FileField(upload_to='inventory/imports/')
    status        = models.CharField(max_length=10, choices=STATUSES, default=STATUS_PENDING, db_index=True)
    total_rows    = models.IntegerField(default=0)
    imported_rows = models.IntegerField(default=0)
    failed_rows   = models.IntegerField(default=0)
    errors        = models.JSONField(null=True, blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        db_table     = 'inventory_import_job'
        ordering     = ['-created_at']
        verbose_name = 'Import job'

    def __str__(self):
        return f'ImportJob #{self.pk} {self.status}'
