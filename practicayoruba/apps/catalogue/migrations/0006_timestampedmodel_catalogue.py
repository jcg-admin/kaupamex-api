"""
Migración de infraestructura: herencia-modelos-django — apps.catalogue

Cambios en BD:
  Category:      ADD created_at + ADD updated_at
  ProductImage:  ADD created_at + ADD updated_at
  SearchHistory: RENAME searched_at → updated_at + ADD created_at
                 (la API mantiene el campo como 'searched_at' via serializer)

Product: refactor puro (ya tenía ambos campos) — sin cambios en BD.
"""
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('catalogue', '0005_productimage_admin_products'),
    ]

    operations = [
        # ─── Category: ADD created_at + updated_at ─────────────────────────
        migrations.AddField(
            model_name='category',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True,
                                       default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='category',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),

        # ─── ProductImage: ADD created_at + updated_at ─────────────────────
        migrations.AddField(
            model_name='productimage',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True,
                                       default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='productimage',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),

        # ─── SearchHistory: RENAME searched_at → updated_at ────────────────
        # H-INH-002: la API mantiene 'searched_at' via source='updated_at'
        migrations.RenameField(
            model_name='searchhistory',
            old_name='searched_at',
            new_name='updated_at',
        ),
        # Actualizar ordering: Meta.ordering=['-updated_at'] en el modelo
        migrations.AlterModelOptions(
            name='searchhistory',
            options={'ordering': ['-updated_at'], 'verbose_name': 'Historial de búsqueda'},
        ),
        # ADD created_at para registrar cuándo se buscó por primera vez
        migrations.AddField(
            model_name='searchhistory',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True,
                                       default=django.utils.timezone.now),
            preserve_default=False,
        ),
    ]
