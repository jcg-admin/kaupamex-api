"""
Cotización de envío — apps.orders.shipping

UC-ORD-01 (política de envío). Punto de extensión ÚNICO (open-closed) del costo
de envío del checkout.

Política vigente (decisión de producto — REVIERTE DEC-BC-25): el envío es
**GRATIS siempre** ($0). El comprador NUNCA selecciona método de envío; el
envío lo configura el admin y la ventana de entrega se deriva automáticamente
por zona (C.P.). El costo hoy es ``Decimal('0.00')`` sin importar subtotal ni
zona.

Punto de extensión (PENDIENTE por decisión de producto):
    "Qué pasa cuando la compra NO alcanza el umbral gratis" está por definir.
    La ÚNICA rama a agregar cuando se decida cobrar envío bajo-umbral vive
    dentro de ``resolve_shipping_quote``: reemplazar el ``cost`` incondicional
    ``Decimal('0.00')`` por la derivación desde la zona
    (``zone.cost`` / ``zone.free_threshold``) cuando ``subtotal`` no alcance
    el umbral. El resto del flujo NO cambia: ``CheckoutView`` consume el
    ``ShippingQuote`` y hace ``shipping_cost = quote.cost`` sea 0 o el costo
    derivado. Así el checkout queda cerrado a modificación y abierto a
    extensión (open-closed): mañana se agrega la rama sin reescribir el flujo.
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from .models import ShippingZone


@dataclass(frozen=True)
class ShippingQuote:
    """Cotización de envío resuelta para un checkout.

    :cost: costo de envío a cobrar (hoy siempre ``Decimal('0.00')``).
    :is_free: True si el envío es gratis (hoy siempre True).
    :zone: ``ShippingZone`` que cubre el C.P., o None si ninguna lo cubre.
    :estimated_days_min: mínimo de días hábiles de entrega en la zona (o None).
    :estimated_days_max: máximo de días hábiles de entrega en la zona (o None).
    """
    cost: Decimal
    is_free: bool
    zone: Optional[ShippingZone]
    estimated_days_min: Optional[int]
    estimated_days_max: Optional[int]


def resolve_shipping_quote(zip_code, subtotal):
    """Resuelve la cotización de envío para un checkout.

    Política vigente: **GRATIS siempre** — ``cost = Decimal('0.00')`` e
    ``is_free = True`` sin importar ``subtotal`` ni la zona. La zona se
    resuelve únicamente para exponer la ventana de entrega (días hábiles).

    :param zip_code: C.P. del domicilio de entrega (str; puede venir vacío).
    :param subtotal: subtotal ya con descuentos aplicados (``Decimal``). Hoy
        NO afecta el costo; se recibe para que el punto de extensión (cobro
        bajo-umbral, PENDIENTE) no cambie la firma cuando se implemente.
    :returns: ``ShippingQuote`` con ``cost`` 0, ``is_free`` True y la ventana
        de entrega de la zona resuelta.
    """
    zone = ShippingZone.resolve_for_zip(zip_code)
    return ShippingQuote(
        cost=Decimal('0.00'),
        is_free=True,
        zone=zone,
        estimated_days_min=zone.estimated_days_min if zone else None,
        estimated_days_max=zone.estimated_days_max if zone else None,
    )
