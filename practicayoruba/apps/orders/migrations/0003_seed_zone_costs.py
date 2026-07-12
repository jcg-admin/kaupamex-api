"""Seed migration — costo de envío + umbral gratis por zona (G-ENV-04).

Registro **en nuestra propia BD** (no dependemos de una API externa de
paqueterías: nosotros guardamos el costo, estilo SEPOMEX). Retira la política
"envío gratis siempre": ahora cuando la compra NO alcanza el umbral se cobra el
costo plano de la zona.

Política (decisión de producto del ejecutor):

- **Metro** (CDMX + Edomex): gratis desde $800; si el subtotal es menor, se
  cobra ``_COST_METRO``.
- **Nacional** (resto): gratis desde $1,300; si es menor, se cobra
  ``_COST_NACIONAL``.

Los importes son valores de arranque para pruebas; el admin los ajusta por
zona desde el panel. Idempotente: fija los valores por prefijo.
"""
from decimal import Decimal
from django.db import migrations

# Prefijos C.P. de CDMX (01/06/14) + Estado de México (53/55/50) = tarifa metro.
_METRO_PREFIXES = {"01", "06", "14", "53", "55", "50"}

_THRESHOLD_METRO    = Decimal("800.00")
_THRESHOLD_NACIONAL = Decimal("1300.00")
_COST_METRO         = Decimal("99.00")     # placeholder de prueba; admin ajusta
_COST_NACIONAL      = Decimal("199.00")    # placeholder de prueba; admin ajusta


def seed_costs(apps, schema_editor):
    ShippingZone = apps.get_model("orders", "ShippingZone")
    for zone in ShippingZone.objects.all():
        if zone.zip_code_prefix in _METRO_PREFIXES:
            zone.free_threshold = _THRESHOLD_METRO
            zone.cost = _COST_METRO
        else:
            zone.free_threshold = _THRESHOLD_NACIONAL
            zone.cost = _COST_NACIONAL
        zone.save(update_fields=["free_threshold", "cost"])


def unseed_costs(apps, schema_editor):
    ShippingZone = apps.get_model("orders", "ShippingZone")
    ShippingZone.objects.all().update(free_threshold=None, cost=None)


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0002_seed_shipping_zones"),
    ]

    operations = [
        migrations.RunPython(seed_costs, unseed_costs),
    ]
