"""Siembra ``ORM Precision`` — ≙ ``decimal_orm_number``.

Fuente: ``odoo19c: odoo/addons/test_orm/data/test_orm_data.xml:48-51``, el
registro de ``decimal.precision`` con tres decimales que lee
``test_orm.mixed.number2``.
"""

from django.db import migrations


def seed_orm_precision(apps, schema_editor):
    DecimalPrecision = apps.get_model('base', 'DecimalPrecision')
    DecimalPrecision.objects.get_or_create(
        name='ORM Precision', defaults={'digits': 3})


def unseed_orm_precision(apps, schema_editor):
    DecimalPrecision = apps.get_model('base', 'DecimalPrecision')
    DecimalPrecision.objects.filter(name='ORM Precision').delete()


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0056_decimalprecision_decimal_precision_name_uniq"),
        ("test_orm", "0033_mixed_number2_amount"),
    ]

    operations = [
        migrations.RunPython(seed_orm_precision, unseed_orm_precision),
    ]
