# ≙ purchase.order.line name (Text), product_no_variant_attribute_value_ids
# y technical_price_unit (odoo19c: purchase_order_line.py:19-20,106,112).

import orm.fields_relational
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('product', '0022_purchase_fields'),
        ('purchase', '0017_line_amounts'),
    ]

    operations = [
        migrations.AddField(
            model_name='purchaseorderline',
            name='product_no_variant_attribute_value_ids',
            field=orm.fields_relational.Many2manyField(
                blank=True, column1='purchase_order_line_id',
                column2='product_template_attribute_value_id',
                db_table=('product_template_attribute_value_'
                          'purchase_order_line_rel'),
                related_name='+',
                to='product.producttemplateattributevalue'),
        ),
        migrations.AddField(
            model_name='purchaseorderline',
            name='technical_price_unit',
            field=models.DecimalField(
                blank=True, decimal_places=4,
                help_text='Technical field for price computation',
                max_digits=16, null=True),
        ),
        migrations.AlterField(
            model_name='purchaseorderline',
            name='name',
            field=models.TextField(
                blank=True, default='',
                help_text='Descripción de la línea (Odoo '
                          'purchase.order.line.name).',
                verbose_name='Description'),
        ),
    ]
