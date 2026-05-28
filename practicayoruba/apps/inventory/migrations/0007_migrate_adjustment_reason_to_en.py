"""
Migration 0007 — T-709: migrate StockMovement.reason values ES → EN.

Moves 6 adjustment_reason values to canonical English:
  CONTEO_FISICO  → PHYSICAL_COUNT
  MERMA          → LOSS
  ROBO           → THEFT
  DEVOLUCION     → RETURN
  DESCONTINUADO  → DISCONTINUED
  OTRO           → OTHER

Generated: 2026-05-28T22:36:57
"""
from django.db import migrations


def migrate_adjustment_reason(apps, schema_editor):
    StockMovement = apps.get_model('inventory', 'StockMovement')
    mapping = {
        'CONTEO_FISICO': 'PHYSICAL_COUNT',
        'MERMA': 'LOSS',
        'ROBO': 'THEFT',
        'DEVOLUCION': 'RETURN',
        'DESCONTINUADO': 'DISCONTINUED',
        'OTRO': 'OTHER',
    }
    for old_val, new_val in mapping.items():
        StockMovement.objects.filter(reason=old_val).update(reason=new_val)


def reverse_migrate_adjustment_reason(apps, schema_editor):
    StockMovement = apps.get_model('inventory', 'StockMovement')
    mapping = {
        'PHYSICAL_COUNT': 'CONTEO_FISICO',
        'LOSS': 'MERMA',
        'THEFT': 'ROBO',
        'RETURN': 'DEVOLUCION',
        'DISCONTINUED': 'DESCONTINUADO',
        'OTHER': 'OTRO',
    }
    for old_val, new_val in mapping.items():
        StockMovement.objects.filter(reason=old_val).update(reason=new_val)


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0006_importjob'),
    ]

    operations = [
        migrations.RunPython(
            migrate_adjustment_reason,
            reverse_migrate_adjustment_reason,
        ),
    ]
