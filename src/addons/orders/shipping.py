"""
Cotización de envío — addons.orders.shipping

UC-ORD-01 (política de envío). Punto de extensión ÚNICO (open-closed) del costo
de envío del checkout.

Política vigente (G-ENV-04): **costo manual por zona con umbral de envío
gratis**. El comprador NUNCA selecciona método de envío; el admin configura,
por zona (C.P.), un ``cost`` opcional y un ``free_threshold`` opcional. El
resolver deriva el costo así:

1. Sin zona, o zona sin ``cost`` configurado  → **GRATIS** (``0.00``). Es la
   política base heredada; las zonas sembradas tienen ``cost=NULL`` y siguen
   gratis hasta que un admin fije un costo (rollout no disruptivo).
2. Zona con ``cost`` y ``free_threshold`` alcanzado por el subtotal → GRATIS.
3. Zona con ``cost`` y subtotal bajo el umbral (o sin umbral) → se cobra el
   ``cost`` manual de la zona.

**Dinero en Decimal, nunca float (IEEE-754).** Todo cálculo monetario usa
``Decimal``; el ``subtotal`` entrante se normaliza con ``Decimal(str(...))``
para neutralizar cualquier artefacto de coma flotante (p. ej.
``0.1+0.2 == 0.30000000000000004``) antes de compararlo con el umbral. Un
error de redondeo en la comparación del umbral podría cobrar envío a una
compra que sí calificaba para gratis (o viceversa).

Open-closed: ``CheckoutView`` consume el ``ShippingQuote`` y hace
``shipping_cost = quote.cost`` sea 0 o el costo derivado; el flujo del checkout
no cambia cuando se ajusta la política de costo — sólo cambia este resolver.
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from addons.delivery.models import ShippingZone

_TWO_PLACES = Decimal('0.01')
_FREE = Decimal('0.00')


@dataclass(frozen=True)
class ShippingQuote:
    """Cotización de envío resuelta para un checkout.

    :cost: costo de envío a cobrar (``Decimal`` de 2 decimales).
    :is_free: True si el envío resultó gratis.
    :zone: ``ShippingZone`` que cubre el C.P., o None si ninguna lo cubre.
    :estimated_days_min: mínimo de días hábiles de entrega en la zona (o None).
    :estimated_days_max: máximo de días hábiles de entrega en la zona (o None).
    """
    cost: Decimal
    is_free: bool
    zone: Optional[ShippingZone]
    estimated_days_min: Optional[int]
    estimated_days_max: Optional[int]


def _to_money(value) -> Decimal:
    """Normaliza un importe a ``Decimal`` de 2 decimales, sin artefacto float.

    Convertir vía ``str`` evita que un ``float`` contaminado por IEEE-754
    (``19.989999999999998``) entre al cálculo monetario. Política del proyecto:
    Decimal para dinero, nunca float sin cuantizar.
    """
    return Decimal(str(value or 0)).quantize(_TWO_PLACES)


def _derive_cost(zone, subtotal) -> tuple[Decimal, bool]:
    """Deriva ``(cost, is_free)`` desde la zona y el subtotal (todo Decimal).

    Reglas (ver docstring del módulo): sin zona/costo → gratis; umbral
    alcanzado → gratis; bajo umbral o sin umbral → cobra ``zone.cost``.
    """
    if zone is None or zone.cost is None:
        return _FREE, True
    subtotal_d = _to_money(subtotal)
    threshold = zone.free_threshold
    if threshold is not None and subtotal_d >= _to_money(threshold):
        return _FREE, True
    return _to_money(zone.cost), False


def resolve_shipping_quote(zip_code, subtotal):
    """Resuelve la cotización de envío para un checkout.

    :param zip_code: C.P. del domicilio de entrega (str; puede venir vacío).
    :param subtotal: subtotal ya con descuentos aplicados (``Decimal``). Se
        compara contra el ``free_threshold`` de la zona; se normaliza a
        ``Decimal`` de forma segura contra float.
    :returns: ``ShippingQuote`` con el costo derivado, ``is_free`` y la ventana
        de entrega de la zona resuelta.
    """
    zone = ShippingZone.resolve_for_zip(zip_code)
    cost, is_free = _derive_cost(zone, subtotal)
    return ShippingQuote(
        cost=cost,
        is_free=is_free,
        zone=zone,
        estimated_days_min=zone.estimated_days_min if zone else None,
        estimated_days_max=zone.estimated_days_max if zone else None,
    )
