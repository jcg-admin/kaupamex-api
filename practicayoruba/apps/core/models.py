"""
apps/core/models.py

TimeStampedModel — clase base abstracta para todos los modelos del proyecto.

Decisiones de diseño documentadas en:
  gestion/herencia-modelos-django/decisiones-herencia-modelos-django.rst

- DEC-001: herencia abstracta (no multi-tabla, no proxy para timestamps)
- DEC-002: una sola clase — CreatedModel descartado (viola DRY y O/C)
- DEC-003: sin db_index en la base — los modelos que lo necesitan lo
           declaran explícitamente (StockMovement, StockAlert, Order)
- DEC-004: sin ordering — cada modelo concreto define el suyo
- DEC-005: User excluido — hereda de AbstractUser de Django
"""
from django.db import models


class TimeStampedModel(models.Model):
    """
    Clase base abstracta que provee created_at y updated_at a todos
    los modelos que hereden de ella.

    Usar en TODOS los modelos concretos del proyecto excepto User.
    No incluye ordering — cada modelo define el suyo.
    No incluye db_index en created_at — los modelos que requieren
    índice por volumen (inventario, órdenes) lo declaran directamente.
    """
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        abstract      = True
        get_latest_by = 'created_at'
