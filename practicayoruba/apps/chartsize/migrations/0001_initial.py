"""Migration Sprint 9 — VariantType, VariantOption, ProductVariant."""
from decimal import Decimal
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True
    dependencies = [
        ('catalogue', '0005_productimage_admin_products'),
    ]

    operations = [
        migrations.CreateModel(
            name='VariantType',
            fields=[
                ('id',        models.BigAutoField(auto_created=True, primary_key=True)),
                ('name',      models.CharField(max_length=100, verbose_name='Nombre del atributo')),
                ('is_active', models.BooleanField(default=True)),
                ('order',     models.PositiveSmallIntegerField(db_index=True, default=0)),
                ('product',   models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='variant_types',
                    to='catalogue.product',
                )),
            ],
            options={'db_table': 'chartsize_variant_type', 'ordering': ['order', 'name']},
        ),
        migrations.AddConstraint(
            model_name='varianttype',
            constraint=models.UniqueConstraint(
                fields=['product', 'name'], name='unique_product_variant_type_name'
            ),
        ),
        migrations.CreateModel(
            name='VariantOption',
            fields=[
                ('id',           models.BigAutoField(auto_created=True, primary_key=True)),
                ('label',        models.CharField(max_length=100)),
                ('slug',         models.SlugField(max_length=120)),
                ('is_active',    models.BooleanField(default=True)),
                ('order',        models.PositiveSmallIntegerField(db_index=True, default=0)),
                ('variant_type', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='options',
                    to='chartsize.varianttype',
                )),
            ],
            options={'db_table': 'chartsize_variant_option', 'ordering': ['order', 'label']},
        ),
        migrations.AddConstraint(
            model_name='variantoption',
            constraint=models.UniqueConstraint(
                fields=['variant_type', 'label'], name='unique_vtype_label'
            ),
        ),
        migrations.AddConstraint(
            model_name='variantoption',
            constraint=models.UniqueConstraint(
                fields=['variant_type', 'slug'], name='unique_vtype_slug'
            ),
        ),
        migrations.CreateModel(
            name='ProductVariant',
            fields=[
                ('id',             models.BigAutoField(auto_created=True, primary_key=True)),
                ('sku_suffix',     models.CharField(blank=True, default='', max_length=20)),
                ('price_override', models.DecimalField(
                    blank=True, null=True, decimal_places=2, max_digits=10,
                    validators=[django.core.validators.MinValueValidator(Decimal('0.01'))],
                )),
                ('stock',          models.PositiveIntegerField(default=0)),
                ('is_active',      models.BooleanField(db_index=True, default=True)),
                ('product',        models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='variants',
                    to='catalogue.product',
                )),
                ('option',         models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='variant',
                    to='chartsize.variantoption',
                )),
            ],
            options={'db_table': 'chartsize_product_variant', 'ordering': ['option__order', 'option__label']},
        ),
    ]
