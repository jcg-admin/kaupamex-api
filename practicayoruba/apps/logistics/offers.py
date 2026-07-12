"""
Motor de cotización de paqueterías — apps.logistics.offers

Adaptación nativa (Django/DRF, no Node/Express) de la "Shipment Offer API":
dado un envío (paquetes con dimensiones/peso/valor/peligrosidad), evalúa cada
paquetería contra sus reglas y devuelve las **elegibles** rankeadas más las
**inelegibles** con el motivo.

Módulo **puro** (sin Django ORM ni I/O): opera sobre ``RateCard`` y dicts, así
que la lógica se testea sin base de datos. El modelo ``CarrierRateCard`` provee
``to_rate_card()`` para alimentarlo desde la BD.

Reglas soportadas por paquetería (cualquiera puede ser None = sin límite):

- ``max_package_weight_kg`` — peso máximo por paquete.
- ``max_length_cm`` / ``max_width_cm`` / ``max_height_cm`` — límite por eje
  (FedEx: 120×80×80). Para "cualquier dimensión ≤ N" (DSV: 100) se fija el mismo
  N en los tres ejes.
- ``max_total_value`` — valor total del envío.
- ``max_total_weight_kg`` — peso total del envío.
- ``allows_hazardous`` — si acepta material peligroso.

Costo = ``base_cost + cost_per_kg × peso_total``. Ranking: costo asc → tránsito
asc → rating ambiental desc.
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

# Rating ambiental → orden (mayor es mejor); el ranking usa el negativo.
ENV_ORDER = {'low': 1, 'medium': 2, 'high': 3}


@dataclass(frozen=True)
class RateCard:
    carrier: str
    base_cost: Decimal
    cost_per_kg: Decimal
    transit_days: int
    environmental: str  # 'low' | 'medium' | 'high'
    max_package_weight_kg: Optional[Decimal] = None
    max_length_cm: Optional[Decimal] = None
    max_width_cm: Optional[Decimal] = None
    max_height_cm: Optional[Decimal] = None
    max_total_value: Optional[Decimal] = None
    max_total_weight_kg: Optional[Decimal] = None
    allows_hazardous: bool = True


def _d(value) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _package_reasons(pkg, rc: RateCard):
    """Motivos por los que un paquete viola las reglas de ``rc`` (lista vacía si
    cumple)."""
    reasons = []
    weight = _d(pkg['weight'])
    if rc.max_package_weight_kg is not None and weight > rc.max_package_weight_kg:
        reasons.append(
            f'{rc.carrier}: paquete de {weight}kg supera el máximo de '
            f'{rc.max_package_weight_kg}kg por paquete.')
    axis_limits = (
        ('length', rc.max_length_cm),
        ('width', rc.max_width_cm),
        ('height', rc.max_height_cm),
    )
    for axis, limit in axis_limits:
        if limit is not None and _d(pkg[axis]) > limit:
            reasons.append(
                f'{rc.carrier}: {axis} de {_d(pkg[axis])}cm supera el máximo '
                f'de {limit}cm.')
    if not rc.allows_hazardous and pkg.get('hazardous'):
        reasons.append(f'{rc.carrier}: no acepta material peligroso.')
    return reasons


def _shipment_reasons(packages, rc: RateCard):
    """Motivos a nivel envío (totales de valor/peso)."""
    reasons = []
    total_value = sum((_d(p['value']) for p in packages), Decimal('0'))
    total_weight = sum((_d(p['weight']) for p in packages), Decimal('0'))
    if rc.max_total_value is not None and total_value > rc.max_total_value:
        reasons.append(
            f'{rc.carrier}: valor total {total_value} supera el máximo de '
            f'{rc.max_total_value}.')
    if rc.max_total_weight_kg is not None and total_weight > rc.max_total_weight_kg:
        reasons.append(
            f'{rc.carrier}: peso total {total_weight}kg supera el máximo de '
            f'{rc.max_total_weight_kg}kg.')
    return reasons


def _total_weight(packages) -> Decimal:
    return sum((_d(p['weight']) for p in packages), Decimal('0'))


def build_offers(packages, rate_cards):
    """Evalúa el envío contra cada ``RateCard``.

    :param packages: lista de dicts ``{length,width,height,weight,value,hazardous?}``.
    :param rate_cards: iterable de ``RateCard``.
    :returns: dict ``{'offers': [...], 'ineligible': [...]}``. ``offers`` viene
        rankeado por costo → tránsito → ambiental (desc).
    """
    total_weight = _total_weight(packages)
    offers = []
    ineligible = []

    for rc in rate_cards:
        reasons = []
        for pkg in packages:
            reasons.extend(_package_reasons(pkg, rc))
        reasons.extend(_shipment_reasons(packages, rc))

        if reasons:
            ineligible.append({'carrier': rc.carrier, 'reasons': reasons})
            continue

        cost = (rc.base_cost + rc.cost_per_kg * total_weight).quantize(Decimal('0.01'))
        offers.append({
            'carrier': rc.carrier,
            'total_cost': cost,
            'transit_days': rc.transit_days,
            'environmental': rc.environmental,
            'rationale': (
                f'Costo = base {rc.base_cost} + {rc.cost_per_kg}/kg × '
                f'{total_weight}kg = {cost}. Tránsito {rc.transit_days} día(s), '
                f'ambiental {rc.environmental}.'),
        })

    # Ranking: costo asc, tránsito asc, ambiental desc (mayor rating primero).
    offers.sort(key=lambda o: (
        o['total_cost'],
        o['transit_days'],
        -ENV_ORDER.get(o['environmental'], 0),
    ))
    return {'offers': offers, 'ineligible': ineligible}
