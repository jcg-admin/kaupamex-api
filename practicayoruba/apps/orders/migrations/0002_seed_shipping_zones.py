"""Seed migration — common MX shipping zones (DEC-BC-18).

Re-encoded as a fresh data migration after the party-model from-scratch
migration regeneration (T-201). The old 0010_seed_shipping_zones (idempotent
get_or_create) was collapsed when migrations were regenerated from models; the
schema regen captures tables only, not RunPython data. This restores the single
canonical seed. Idempotent by zip_code_prefix.
"""
from django.db import migrations


ZONES = [
    ("Ciudad de México - Norte", "01"),
    ("Ciudad de México - Centro", "06"),
    ("Ciudad de México - Sur", "14"),
    ("Guadalajara, JAL", "44"),
    ("Zapopan, JAL", "45"),
    ("Monterrey, NL", "64"),
    ("San Nicolás, NL", "66"),
    ("Naucalpan, MEX", "53"),
    ("Ecatepec, MEX", "55"),
    ("Toluca, MEX", "50"),
    ("Puebla, PUE", "72"),
    ("Veracruz, VER", "91"),
    ("León, GTO", "37"),
    ("Querétaro, QRO", "76"),
    ("Mérida, YUC", "97"),
    ("Tijuana, BC", "22"),
    ("Hermosillo, SON", "83"),
    ("Chihuahua, CHIH", "31"),
    ("Saltillo, COAH", "25"),
    ("Tampico, TAMPS", "89"),
    ("Matamoros, TAMPS", "87"),
    ("Villahermosa, TAB", "86"),
    ("Oaxaca, OAX", "68"),
    ("Acapulco, GRO", "39"),
    ("Cuernavaca, MOR", "62"),
    ("Aguascalientes, AGS", "20"),
    ("Culiacán, SIN", "80"),
    ("San Luis Potosí, SLP", "78"),
]


def seed_zones(apps, schema_editor):
    # Idempotente por prefijo (H-API-07). get_or_create respeta el invariante
    # unique(zip_code_prefix). Si dos entradas comparten prefijo, gana la
    # primera.
    ShippingZone = apps.get_model("orders", "ShippingZone")
    for name, prefix in ZONES:
        ShippingZone.objects.get_or_create(
            zip_code_prefix=prefix, defaults={"name": name, "is_active": True},
        )


def unseed_zones(apps, schema_editor):
    ShippingZone = apps.get_model("orders", "ShippingZone")
    ShippingZone.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_zones, reverse_code=unseed_zones),
    ]
