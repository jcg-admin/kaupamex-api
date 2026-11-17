"""El `default` de la moneda de la tarifa de proveedor (``odoo19c:
product_supplierinfo.py:36-39``): la de la empresa activa."""

import addons.product.models.product_supplierinfo
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0117_respartner_buyer_id"),
        ("product", "0022_purchase_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="productsupplierinfo",
            name="currency",
            field=models.ForeignKey(
                blank=True,
                default=(addons.product.models.product_supplierinfo
                         ._default_currency),
                help_text=(
                    "Moneda en que el proveedor cotiza. Requerido en la "
                    "referencia, con la de la compañía por defecto."),
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="supplierinfo_ids",
                to="base.rescurrency",
                verbose_name="Moneda",
            ),
        ),
    ]
