"""
Seed de paqueterías + tarifas de ejemplo para el motor de cotización
(apps.logistics.offers / ShipmentOffersView).

Adaptación nativa de la "Shipment Offer API": el catálogo original venía
en EUR; aquí las tarifas se expresan en MXN (moneda de la tienda) y son
**datos de ejemplo ilustrativos**, no tarifas contratadas reales. Ajustar
por el operador desde el admin cuando existan tarifas reales.

Idempotente: ``update_or_create`` por ``code`` del courier y por el
OneToOne del rate card. Correr:

    python manage.py seed_rate_cards
"""
from decimal import Decimal
from django.core.management.base import BaseCommand
from apps.logistics.models import CarrierRateCard, Courier

# (code, name, rate_card_kwargs). Reglas ``None`` = sin límite.
CARRIERS = [
    ('dhl', 'DHL', dict(
        base_cost=Decimal('120.00'), cost_per_kg=Decimal('18.00'),
        transit_days=2, environmental=CarrierRateCard.ENV_MEDIUM,
        max_package_weight_kg=Decimal('70.00'),
        max_total_weight_kg=Decimal('300.00'),
        allows_hazardous=False,
    )),
    ('bring', 'Bring', dict(
        base_cost=Decimal('90.00'), cost_per_kg=Decimal('22.00'),
        transit_days=4, environmental=CarrierRateCard.ENV_HIGH,
        max_package_weight_kg=Decimal('35.00'),
        max_total_value=Decimal('50000.00'),
        allows_hazardous=False,
    )),
    ('fedex', 'FedEx', dict(
        base_cost=Decimal('150.00'), cost_per_kg=Decimal('15.00'),
        transit_days=1, environmental=CarrierRateCard.ENV_LOW,
        max_package_weight_kg=Decimal('68.00'),
        max_length_cm=Decimal('120.00'),
        max_width_cm=Decimal('80.00'),
        max_height_cm=Decimal('80.00'),
        allows_hazardous=True,
    )),
    ('dsv-green', 'DSV Green', dict(
        base_cost=Decimal('80.00'), cost_per_kg=Decimal('25.00'),
        transit_days=5, environmental=CarrierRateCard.ENV_HIGH,
        # "cualquier dimensión ≤ 100 cm" → mismo límite en los tres ejes.
        max_length_cm=Decimal('100.00'),
        max_width_cm=Decimal('100.00'),
        max_height_cm=Decimal('100.00'),
        max_total_weight_kg=Decimal('150.00'),
        allows_hazardous=False,
    )),
]


class Command(BaseCommand):
    help = 'Seed carriers + rate cards de ejemplo para el motor de cotización.'

    def handle(self, *args, **options):
        created = 0
        for code, name, rc_kwargs in CARRIERS:
            courier, _ = Courier.objects.update_or_create(
                code=code, defaults={'name': name, 'is_active': True})
            _, was_created = CarrierRateCard.objects.update_or_create(
                courier=courier,
                defaults={**rc_kwargs, 'is_active': True})
            created += int(was_created)
            self.stdout.write(f'  rate card {name} ({"nuevo" if was_created else "actualizado"})')
        self.stdout.write(self.style.SUCCESS(
            f'Seed rate cards OK: {len(CARRIERS)} paqueterías ({created} nuevas).'))
