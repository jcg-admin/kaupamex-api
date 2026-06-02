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
    # NO-OP (H-API-07): esta migracion era un SEED DUPLICADO de
    # 0010_seed_shipping_zones (mal merge: ramas 0009/0011 paralelas). Sembrar
    # de nuevo creaba 2 zonas por prefijo -> MultipleObjectsReturned. El seed
    # canonico e idempotente es 0010. Aqui no se siembra nada. La lista ZONES
    # se conserva solo como referencia historica del contenido duplicado.
    return


def unseed_zones(apps, schema_editor):
    # NO-OP: el reverse de un seed que ya no siembra no debe borrar zonas
    # (las creo 0010). Borrarlas aqui destruiria datos legitimos.
    return


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0011_shipping_zone'),
    ]

    operations = [
        migrations.RunPython(seed_zones, unseed_zones),
    ]
