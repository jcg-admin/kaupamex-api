"""
Proxy models — apps.inventory
Sprint de infraestructura: herencia-modelos-django (T-012)

Tipo de herencia: PROXY (DEC-006).
- Misma tabla: inventory_stock_movement
- Comportamiento Python distinto por tipo de movimiento
- Sin migraciones nuevas

Uso:
    from apps.inventory.proxy_models import SaleMovement, AdjustmentMovement
    SaleMovement.objects.all()          # solo movimientos SALE
    AdjustmentMovement.objects.filter(product=p)  # solo ADJUSTMENT
"""
from django.db import models
from .models import StockMovement



# =============================================================================
# Managers
# =============================================================================

class SaleMovementManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(movement_type=StockMovement.TYPE_SALE)


class CancellationMovementManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(movement_type=StockMovement.TYPE_CANCELLATION)


class AdjustmentMovementManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(movement_type=StockMovement.TYPE_ADJUSTMENT)


class ImportMovementManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(movement_type=StockMovement.TYPE_IMPORT)


# =============================================================================
# Proxy Models
# =============================================================================

class SaleMovement(StockMovement):
    """
    Movimientos de stock de tipo SALE.
    Se crean durante el checkout (UC-ORD-01).
    delta siempre negativo (decremento de stock).
    """
    objects = SaleMovementManager()

    class Meta:
        proxy        = True
        verbose_name = 'Movimiento de venta'

    def save(self, *args, **kwargs):
        self.movement_type = StockMovement.TYPE_SALE
        super().save(*args, **kwargs)


class CancellationMovement(StockMovement):
    """
    Movimientos de stock de tipo CANCELLATION.
    Se crean al cancelar una orden (UC-ORD-04).
    delta siempre positivo (restauración de stock).
    """
    objects = CancellationMovementManager()

    class Meta:
        proxy        = True
        verbose_name = 'Movimiento de cancelación'

    def save(self, *args, **kwargs):
        self.movement_type = StockMovement.TYPE_CANCELLATION
        super().save(*args, **kwargs)


class AdjustmentMovement(StockMovement):
    """
    Movimientos de stock de tipo ADJUSTMENT.
    Se crean desde el panel admin (UC-INV-04).
    delta positivo (entrada) o negativo (salida/merma).
    reference = 'ADMIN:<user_pk>'
    """
    objects = AdjustmentMovementManager()

    class Meta:
        proxy        = True
        verbose_name = 'Ajuste manual de stock'

    def save(self, *args, **kwargs):
        self.movement_type = StockMovement.TYPE_ADJUSTMENT
        super().save(*args, **kwargs)


class ImportMovement(StockMovement):
    """
    Movimientos de stock de tipo IMPORT.
    Se crean durante la importación masiva CSV (UC-INV-05).
    delta siempre positivo (alta de stock por importación).
    """
    objects = ImportMovementManager()

    class Meta:
        proxy        = True
        verbose_name = 'Movimiento de importación'

    def save(self, *args, **kwargs):
        self.movement_type = StockMovement.TYPE_IMPORT
        super().save(*args, **kwargs)
