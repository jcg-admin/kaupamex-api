# ≙ purchase.order.line tax_ids, product_qty y los importes almacenados
# (odoo19c: purchase_order_line.py:23,34,46-48,106-136). Las líneas
# existentes reciben sus importes del motor de account.tax, y su
# price_total_cc se recalcula sobre el subtotal nuevo.

import orm.fields_relational
from django.db import migrations, models

from orm.migration_operations import ComputeStoredFields


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0039_parent_state'),
        ('purchase', '0016_line_product_uom_qty'),
    ]

    operations = [
        migrations.AddField(
            model_name='purchaseorderline',
            name='price_subtotal',
            field=models.DecimalField(
                blank=True, decimal_places=2, editable=False,
                max_digits=16, null=True, verbose_name='Subtotal'),
        ),
        migrations.AddField(
            model_name='purchaseorderline',
            name='price_tax',
            field=models.DecimalField(
                blank=True, decimal_places=2, editable=False,
                max_digits=16, null=True, verbose_name='Tax'),
        ),
        migrations.AddField(
            model_name='purchaseorderline',
            name='price_total',
            field=models.DecimalField(
                blank=True, decimal_places=2, editable=False,
                max_digits=16, null=True, verbose_name='Total'),
        ),
        migrations.AddField(
            model_name='purchaseorderline',
            name='tax_ids',
            field=orm.fields_relational.Many2manyField(
                blank=True, column1='purchase_order_line_id',
                column2='account_tax_id',
                db_table='account_tax_purchase_order_line_rel',
                related_name='+', to='account.accounttax'),
        ),
        migrations.AlterField(
            model_name='purchaseorderline',
            name='product_qty',
            field=models.DecimalField(
                decimal_places=4,
                help_text='Odoo product_qty (digits="Product Unit", '
                          'required).',
                max_digits=16, verbose_name='Quantity'),
        ),
        # price_total_cc (purchase_requisition) pasa a calculado almacenado
        # sobre price_subtotal (odoo19c: purchase_requisition/models/
        # purchase.py:257-263).
        migrations.AlterField(
            model_name='purchaseorderline',
            name='price_total_cc',
            field=models.DecimalField(
                blank=True, decimal_places=2, editable=False,
                help_text='Odoo price_total_cc ("Company Subtotal", compute, '
                          'store=True, currency_field=\'company_currency_id\''
                          ' — sin receptor aquí, ver docstring del módulo). '
                          '``price_subtotal`` / ``order_id.currency_rate``.',
                max_digits=12, null=True,
                verbose_name='Subtotal en moneda de la empresa'),
        ),
        ComputeStoredFields('purchase', 'purchaseorderline',
                            ['price_subtotal', 'price_total', 'price_tax',
                             'price_total_cc']),
    ]
