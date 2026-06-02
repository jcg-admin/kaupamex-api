# H-API-07 (2026-06-02): impone el invariante UNA zona por zip_code_prefix.
# Contexto: un mal merge dejo dos seeds (0010 + 0012) que con bulk_create
# sembraban 2 zonas por prefijo en un migrate fresco -> get_or_create(
# zip_code_prefix=...) daba MultipleObjectsReturned. 0010 quedo idempotente y
# 0012 quedo no-op; esta migracion limpia los entornos YA migrados (incluida
# produccion, que corrio ambos seeds) y agrega el constraint unique.
from django.db import migrations, models


def dedupe_zones(apps, schema_editor):
    """Dejar UNA zona por zip_code_prefix (la de menor id). Necesario ANTES de
    imponer unique(zip_code_prefix): si hay filas duplicadas (caso produccion
    con el seed duplicado ya aplicado), el AlterField fallaria. DML via ORM
    (no schema_editor.execute — H-API-01). Sin FKs hacia ShippingZone, el
    delete es seguro (no cascada/protect)."""
    ShippingZone = apps.get_model('orders', 'ShippingZone')
    seen = set()
    for zone in ShippingZone.objects.order_by('id').iterator():
        if zone.zip_code_prefix in seen:
            zone.delete()
        else:
            seen.add(zone.zip_code_prefix)


class Migration(migrations.Migration):

    # MariaDB no puede envolver DDL (AlterField) + RunPython en una transaccion
    # reversible (can_rollback_ddl=False). atomic=False evita el
    # TransactionManagementError, mismo patron que catalogue/0016 (H-API-01).
    atomic = False

    dependencies = [
        ('orders', '0016_migrate_order_status_pagada_to_paid'),
    ]

    operations = [
        # 1) deduplicar ANTES del constraint (envs ya migrados / produccion).
        migrations.RunPython(dedupe_zones, migrations.RunPython.noop),
        # 2) imponer el invariante a nivel BD (una zona por prefijo).
        migrations.AlterField(
            model_name='shippingzone',
            name='zip_code_prefix',
            field=models.CharField(max_length=5, unique=True),
        ),
    ]
