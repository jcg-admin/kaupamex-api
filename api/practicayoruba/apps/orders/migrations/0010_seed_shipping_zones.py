"""Seed migration — common MX shipping zones (DEC-BC-18)."""
from django.db import migrations


ZONES = [
    # CDMX (01-16)
    ("Ciudad de México - Norte", "01"),
    ("Ciudad de México - Centro", "06"),
    ("Ciudad de México - Sur", "14"),
    # Jalisco
    ("Guadalajara, JAL", "44"),
    ("Zapopan, JAL", "45"),
    # Nuevo León
    ("Monterrey, NL", "64"),
    ("San Nicolás, NL", "66"),
    # Estado de México
    ("Naucalpan, MEX", "53"),
    ("Ecatepec, MEX", "55"),
    ("Toluca, MEX", "50"),
    # Puebla
    ("Puebla, PUE", "72"),
    # Veracruz
    ("Veracruz, VER", "91"),
    ("Xalapa, VER", "91"),
    # Guanajuato
    ("León, GTO", "37"),
    # Querétaro
    ("Querétaro, QRO", "76"),
    # Yucatán
    ("Mérida, YUC", "97"),
    # Baja California
    ("Tijuana, BC", "22"),
    # Sonora
    ("Hermosillo, SON", "83"),
    # Chihuahua
    ("Chihuahua, CHIH", "31"),
    # Coahuila
    ("Saltillo, COAH", "25"),
    # Tamaulipas
    ("Tampico, TAMPS", "89"),
    ("Matamoros, TAMPS", "87"),
    # Tabasco
    ("Villahermosa, TAB", "86"),
    # Oaxaca
    ("Oaxaca, OAX", "68"),
    # Guerrero
    ("Acapulco, GRO", "39"),
    # Morelos
    ("Cuernavaca, MOR", "62"),
    # Aguascalientes
    ("Aguascalientes, AGS", "20"),
    # Sinaloa
    ("Culiacán, SIN", "80"),
    # San Luis Potosí
    ("San Luis Potosí, SLP", "78"),
]


def seed_zones(apps, schema_editor):
    ShippingZone = apps.get_model("orders", "ShippingZone")
    ShippingZone.objects.bulk_create([
        ShippingZone(name=name, zip_code_prefix=prefix, is_active=True)
        for name, prefix in ZONES
    ])


def unseed_zones(apps, schema_editor):
    ShippingZone = apps.get_model("orders", "ShippingZone")
    ShippingZone.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0009_shipping_zone"),
    ]

    operations = [
        migrations.RunPython(seed_zones, reverse_code=unseed_zones),
    ]
