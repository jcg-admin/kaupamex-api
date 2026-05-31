from django.db import migrations

ZONES = [
    ('CDMX Centro',               '01'),
    ('CDMX Cuauhtémoc',           '06'),
    ('CDMX Tlalpan',              '14'),
    ('Guadalajara',               '44'),
    ('Zapopan',                   '45'),
    ('Monterrey',                 '64'),
    ('San Nicolás de los Garza',  '66'),
    ('Edo. México Tlalnepantla',  '53'),
    ('Edo. México Ecatepec',      '55'),
    ('Edo. México Toluca',        '50'),
    ('Puebla',                    '72'),
    ('Veracruz',                  '91'),
    ('León',                      '37'),
    ('Querétaro',                 '76'),
    ('Mérida',                    '97'),
    ('Tijuana',                   '22'),
    ('Hermosillo',                '83'),
    ('Chihuahua',                 '31'),
    ('Saltillo',                  '25'),
    ('Tampico',                   '89'),
    ('Matamoros',                 '87'),
    ('Villahermosa',              '86'),
    ('Oaxaca',                    '68'),
    ('Acapulco',                  '39'),
    ('Cuernavaca',                '62'),
    ('Aguascalientes',            '20'),
    ('Culiacán',                  '80'),
    ('San Luis Potosí',           '78'),
]


def seed_zones(apps, schema_editor):
    ShippingZone = apps.get_model('orders', 'ShippingZone')
    ShippingZone.objects.bulk_create([
        ShippingZone(name=name, zip_code_prefix=prefix, is_active=True)
        for name, prefix in ZONES
    ])


def unseed_zones(apps, schema_editor):
    ShippingZone = apps.get_model('orders', 'ShippingZone')
    ShippingZone.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0011_shipping_zone'),
    ]

    operations = [
        migrations.RunPython(seed_zones, unseed_zones),
    ]
