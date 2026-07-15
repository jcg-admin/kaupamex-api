"""
InventoryService — apps.inventory
Sprint 10 — UC-INV-02 (Decrementar), UC-INV-03 (Restaurar), UC-INV-04 (Ajuste)

Este servicio es el punto central de toda mutacion de stock.
Se llama desde:
- Sprint 10: directamente en tests (sin ordenes)
- Sprint 12: desde apps.cart al hacer checkout
- Sprint 18: desde apps.orders al confirmar pago (UC-ORD-07)
"""
import logging
from datetime import timedelta
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from apps.settings_app.models import SiteSettings
from .models import StockAlert, StockMovement
from apps.catalogue.models import Product
from apps.chartsize.models import ProductVariant


logger = logging.getLogger('apps')


class InsufficientStockError(Exception):
    """Stock insuficiente para completar la operacion."""
    def __init__(self, product_sku, variant_label=None, available=0, requested=0):
        self.product_sku  = product_sku
        self.variant_label = variant_label
        self.available    = available
        self.requested    = requested
        msg = (f'Stock insuficiente para {product_sku}'
               + (f' ({variant_label})' if variant_label else '')
               + f': disponible={available}, solicitado={requested}')
        super().__init__(msg)


def _get_stock_status(stock: int, threshold: int) -> str:
    """Calcula el estado de stock respecto al umbral."""
    if stock == 0:
        return 'AGOTADO'
    if stock <= threshold:
        return 'BAJO'
    return 'NORMAL'


def _maybe_create_alert(product, variant, new_stock: int) -> None:
    """
    Crea StockAlert si el stock cae bajo el umbral y no hay alerta reciente.
    Deduplicacion: 24 horas. FR-INV-02.02.
    """

    threshold = SiteSettings.get_current().min_stock_threshold
    if new_stock > threshold:
        return

    cutoff = timezone.now() - timedelta(hours=24)
    with transaction.atomic():
        already = StockAlert.objects.select_for_update().filter(
            product=product, resolved=False, created_at__gte=cutoff
        )
        if variant:
            already = already.filter(variant=variant)
        if already.exists():
            return

        StockAlert.objects.create(
            product=product,
            variant=variant,
            stock_at_alert=new_stock,
        )
        logger.info(
            'StockAlert creada: %s%s stock=%d umbral=%d',
            product.sku,
            f'/{variant.option.label}' if variant else '',
            new_stock, threshold,
        )


def _resolve_open_alerts(product, variant, new_stock: int) -> None:
    """
    Resuelve las StockAlert abiertas del producto/variante cuando el stock
    vuelve a estar por encima del umbral tras una entrada de mercancia.
    Mirror de la deduplicacion de _maybe_create_alert. UC-INV (restock).
    """
    threshold = SiteSettings.get_current().min_stock_threshold
    if new_stock <= threshold:
        return

    with transaction.atomic():
        open_alerts = StockAlert.objects.select_for_update().filter(
            product=product, resolved=False,
        )
        if variant:
            open_alerts = open_alerts.filter(variant=variant)
        else:
            open_alerts = open_alerts.filter(variant__isnull=True)
        for alert in open_alerts:
            alert.resolved = True
            alert.resolved_at = timezone.now()
            alert.save(update_fields=['resolved', 'resolved_at'])


class InventoryService:
    """
    Servicio de inventario. Todas las operaciones son atomicas.
    """

    @staticmethod
    def restock(product, variant=None, quantity: int = 0,
                reference: str = '', notes: str = '', created_by=None):
        """
        Entrada de stock (restock / reabastecimiento). UC-INV.

        Incrementa el stock de la variante (o producto) en `quantity`,
        registra un StockMovement de tipo RESTOCK con delta=+quantity y la
        referencia de compra, y resuelve cualquier StockAlert abierta si el
        stock supera el umbral.

        A diferencia de adjust(), restock SIEMPRE es una entrada positiva
        ligada a una recepcion de mercancia (reference = orden de compra).

        quantity debe ser > 0 — en caso contrario lanza ValueError.
        Usa SELECT FOR UPDATE para prevenir condiciones de carrera (BR-004).
        """
        if quantity <= 0:
            raise ValueError(
                f'La cantidad de entrada debe ser positiva (recibido: {quantity}).'
            )

        with transaction.atomic():
            if variant:
                v = ProductVariant.objects.select_for_update().get(pk=variant.pk)
                stock_before = v.stock
                v.stock += quantity
                v.save(update_fields=['stock', 'updated_at'])
                stock_after = v.stock
            else:
                p = Product.objects.select_for_update().get(pk=product.pk)
                stock_before = p.stock
                p.stock += quantity
                p.save(update_fields=['stock', 'updated_at'])
                stock_after = p.stock

            mov = StockMovement.objects.create(
                product=product, variant=variant,
                delta=quantity, stock_before=stock_before,
                stock_after=stock_after,
                movement_type=StockMovement.TYPE_RESTOCK,
                reference=reference, notes=notes, created_by=created_by,
            )
            _resolve_open_alerts(product, variant, stock_after)
            return mov

    @staticmethod
    def decrement(items, reference: str = '', created_by=None) -> list:
        """
        Decrementa el stock de una lista de items.

        Cada item debe tener:
          - 'product': instancia Product
          - 'variant': instancia ProductVariant o None
          - 'quantity': int > 0

        Usa SELECT FOR UPDATE para prevenir condiciones de carrera (BR-004).
        Si algún item no tiene stock suficiente, lanza InsufficientStockError
        y hace rollback de toda la transaccion.

        Retorna lista de StockMovement creados.
        UC-INV-02 (FR-INV-02.02).
        """

        movements = []

        with transaction.atomic():
            for item in items:
                product  = item['product']
                variant  = item.get('variant')
                quantity = item['quantity']

                if variant:
                    # Bloquear la fila de la variante
                    v = ProductVariant.objects.select_for_update().get(pk=variant.pk)
                    if v.stock < quantity:
                        raise InsufficientStockError(
                            product.sku, v.option.label, v.stock, quantity
                        )
                    stock_before = v.stock
                    v.stock -= quantity
                    v.save(update_fields=['stock', 'updated_at'])
                    stock_after = v.stock
                else:
                    p = Product.objects.select_for_update().get(pk=product.pk)
                    if p.stock < quantity:
                        raise InsufficientStockError(
                            p.sku, None, p.stock, quantity
                        )
                    stock_before = p.stock
                    p.stock -= quantity
                    p.save(update_fields=['stock', 'updated_at'])
                    stock_after = p.stock

                mov = StockMovement.objects.create(
                    product=product, variant=variant,
                    delta=-quantity, stock_before=stock_before,
                    stock_after=stock_after,
                    movement_type=StockMovement.TYPE_SALE,
                    reference=reference, created_by=created_by,
                )
                movements.append(mov)
                _maybe_create_alert(product, variant, stock_after)

        return movements

    @staticmethod
    def restore(items, reference: str = '', created_by=None) -> list:
        """
        Restaura el stock (usado en cancelaciones de orden). UC-INV-03.
        Idempotente: si ya existe un StockMovement CANCELLATION con la misma
        reference + product + variant, no crea duplicado.
        """

        movements = []
        with transaction.atomic():
            for item in items:
                product  = item['product']
                variant  = item.get('variant')
                quantity = item['quantity']

                # Idempotencia
                if reference:
                    exists = StockMovement.objects.filter(
                        product=product, variant=variant,
                        movement_type=StockMovement.TYPE_CANCELLATION,
                        reference=reference,
                    ).exists()
                    if exists:
                        continue

                if variant:
                    v = ProductVariant.objects.select_for_update().get(pk=variant.pk)
                    stock_before = v.stock
                    v.stock += quantity
                    v.save(update_fields=['stock', 'updated_at'])
                    stock_after = v.stock
                else:
                    p = Product.objects.select_for_update().get(pk=product.pk)
                    stock_before = p.stock
                    p.stock += quantity
                    p.save(update_fields=['stock', 'updated_at'])
                    stock_after = p.stock

                mov = StockMovement.objects.create(
                    product=product, variant=variant,
                    delta=+quantity, stock_before=stock_before,
                    stock_after=stock_after,
                    movement_type=StockMovement.TYPE_CANCELLATION,
                    reference=reference, created_by=created_by,
                )
                movements.append(mov)

        return movements

    @staticmethod
    def adjust(product, variant=None, delta: int = 0,
               notes: str = '', reason: str = '', created_by=None):
        """
        Ajuste manual de stock por delta. UC-INV-04 (FR-INV-04.02).
        delta positivo = entrada de mercancía.
        delta negativo = salida / corrección a la baja.
        Si stock_actual + delta < 0 → lanza ValueError.
        Referencia de auditoría: ADMIN:<created_by.pk>.
        reason: código estructurado del motivo (PHYSICAL_COUNT, LOSS, etc.).
        """

        with transaction.atomic():
            if variant:
                v = ProductVariant.objects.select_for_update().get(pk=variant.pk)
                stock_before = v.stock
                new_stock = v.stock + delta
                if new_stock < 0:
                    raise ValueError(
                        f'El ajuste resultaría en stock negativo ({new_stock}).'
                    )
                v.stock = new_stock
                v.save(update_fields=['stock', 'updated_at'])
                stock_after = new_stock
            else:
                p = Product.objects.select_for_update().get(pk=product.pk)
                stock_before = p.stock
                new_stock = p.stock + delta
                if new_stock < 0:
                    raise ValueError(
                        f'El ajuste resultaría en stock negativo ({new_stock}).'
                    )
                p.stock = new_stock
                p.save(update_fields=['stock', 'updated_at'])
                stock_after = new_stock

            reference = f'ADMIN:{created_by.pk}' if created_by else 'ADMIN'
            mov = StockMovement.objects.create(
                product=product, variant=variant,
                delta=delta, stock_before=stock_before,
                stock_after=stock_after,
                movement_type=StockMovement.TYPE_ADJUSTMENT,
                reason=reason, reference=reference,
                notes=notes, created_by=created_by,
            )
            _maybe_create_alert(product, variant, stock_after)
            return mov

    @staticmethod
    def check_availability(items) -> list:
        """
        Verifica disponibilidad de stock sin modificarlo.
        Retorna lista de items insuficientes (vacia si todos estan OK).
        Usado por el checkout (Sprint 14) antes de procesar el pago.

        H-CICLO42-02: incluye verificacion de product.is_active y
        product.is_published. Sin esta guardia un producto desactivado
        podia atravesar el checkout con stock ficticiamente "disponible".
        """
        insufficient = []
        for item in items:
            product  = item['product']
            variant  = item.get('variant')
            quantity = item['quantity']
            # Producto desactivado o no publicado — tratar como stock 0.
            if not (product.is_active and product.is_published):
                insufficient.append({
                    'sku':       product.sku,
                    'variant':   variant.option.label if variant else None,
                    'available': 0,
                    'requested': quantity,
                })
                continue
            available = variant.stock if variant else product.stock
            if available < quantity:
                insufficient.append({
                    'sku':       product.sku,
                    'variant':   variant.option.label if variant else None,
                    'available': available,
                    'requested': quantity,
                })
        return insufficient
