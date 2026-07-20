"""
Seed de paqueterías + tarifas para el motor de cotización
(addons.delivery.offers / ShipmentOffersView).

Catálogo canónico (spec del ejecutor): DHL / Bring / FedEx Express /
DSV Green. La spec viene en **EUR**; aquí se adapta a **MXN** (moneda de la
tienda) multiplicando por ``_EUR_MXN``, una tasa **ilustrativa** — NO una
cotización FX real. El operador/ops fija las tarifas reales desde el admin.
La conversión se deja explícita (``base_eur * _EUR_MXN``) para que la
relación con la spec sea trazable y re-derivable.

Costo del envío = ``base + per_kg × peso_total`` (ver offers.py). Reglas por
paquetería adaptadas 1:1 de la spec.

Idempotente (``update_or_create`` por code). Correr:

    python manage.py seed_rate_cards
"""
from decimal import Decimal
from django.core.management.base import BaseCommand
from addons.delivery.models import CarrierRateCard, Courier

# Tasa ILUSTRATIVA EUR→MXN (placeholder; el operador ajusta tarifas reales).
_EUR_MXN = Decimal('20')


def _mxn(eur) -> Decimal:
    return (Decimal(str(eur)) * _EUR_MXN).quantize(Decimal('0.01'))


# (code, name, base_eur, per_kg_eur, transit, environmental, rules).
# Reglas None = sin límite. allows_hazardous=True salvo que la spec lo prohíba.
CARRIERS = [
    ('dhl', 'DHL', '100', '5', 2, CarrierRateCard.ENV_MEDIUM, dict(
        max_package_weight_kg=Decimal('50'),
        allows_hazardous=False,                 # spec: "No hazardous materials"
    )),
    ('bring', 'Bring', '80', '4', 3, CarrierRateCard.ENV_HIGH, dict(
        max_package_weight_kg=Decimal('30'),
        max_total_value=_mxn('5000'),           # spec: "Max total value €5,000"
        allows_hazardous=True,
    )),
    ('fedex', 'FedEx Express', '150', '6', 1, CarrierRateCard.ENV_LOW, dict(
        max_package_weight_kg=Decimal('70'),
        max_length_cm=Decimal('120'),           # spec: 120×80×80 cm
        max_width_cm=Decimal('80'),
        max_height_cm=Decimal('80'),
        allows_hazardous=True,
    )),
    ('dsv-green', 'DSV Green', '90', '4.50', 4, CarrierRateCard.ENV_HIGH, dict(
        max_package_weight_kg=Decimal('40'),
        # spec: "No packages over 100cm in any dimension" → mismo límite/eje.
        max_length_cm=Decimal('100'),
        max_width_cm=Decimal('100'),
        max_height_cm=Decimal('100'),
        max_total_weight_kg=Decimal('200'),     # spec: "Total shipment ≤ 200kg"
        allows_hazardous=True,
    )),
]


class Command(BaseCommand):
    help = 'Seed carriers + rate cards (catálogo canónico DHL/Bring/FedEx/DSV, MXN).'

    def handle(self, *args, **options):
        created = 0
        for code, name, base_eur, per_kg_eur, transit, env, rules in CARRIERS:
            courier, _ = Courier.objects.update_or_create(
                code=code, defaults={'name': name, 'is_active': True})
            defaults = {
                'base_cost': _mxn(base_eur),
                'cost_per_kg': _mxn(per_kg_eur),
                'transit_days': transit,
                'environmental': env,
                'is_active': True,
                **rules,
            }
            _, was_created = CarrierRateCard.objects.update_or_create(
                courier=courier, defaults=defaults)
            created += int(was_created)
            self.stdout.write(
                f'  {name}: base {defaults["base_cost"]} + '
                f'{defaults["cost_per_kg"]}/kg ({"nuevo" if was_created else "actualizado"})')
        self.stdout.write(self.style.SUCCESS(
            f'Seed rate cards OK: {len(CARRIERS)} paqueterías '
            f'(EUR→MXN ×{_EUR_MXN} ilustrativa; {created} nuevas).'))
