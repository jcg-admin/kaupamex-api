"""
Migration Sprint 7:
- Agrega modelo ProductImage (declarado ahora, gestionado desde Sprint 8).
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0004_searchhistory_caches'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProductImage',
            fields=[
                ('id',       models.BigAutoField(auto_created=True, primary_key=True)),
                ('image',    models.ImageField(upload_to='products/%Y/%m/')),
                ('alt_text', models.CharField(blank=True, default='', max_length=200)),
                ('order',    models.PositiveSmallIntegerField(db_index=True, default=0)),
                ('product',  models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='images',
                    to='catalogue.product',
                )),
            ],
            options={
                'db_table': 'catalogue_product_image',
                'ordering': ['order', 'id'],
            },
        ),
    ]
