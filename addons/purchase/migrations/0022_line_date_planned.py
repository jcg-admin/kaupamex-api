"""``date_planned`` de ``purchase.order.line`` (``odoo19c:
purchase_order_line.py:25-28``), calculado sobre las filas existentes."""

from django.db import migrations, models

from orm.migration_operations import ComputeStoredFields


class Migration(migrations.Migration):

    dependencies = [
        ("purchase", "0021_order_fiscal_header"),
    ]

    operations = [
        migrations.AddField(
            model_name="purchaseorderline",
            name="date_planned",
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                help_text=(
                    "Delivery date expected from vendor. This date "
                    "respectively defaults to vendor pricelist lead time "
                    "then today's date."),
                null=True,
                verbose_name="Expected Arrival",
            ),
        ),
        ComputeStoredFields(
            "purchase", "purchaseorderline", ["date_planned"]),
    ]
