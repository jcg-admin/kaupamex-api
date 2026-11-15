"""El proveedor de ``purchase.order`` pasa de ``res.users`` a
``res.partner`` (``odoo19c: purchase_order.py:91-94``), y la línea gana su
``partner_id`` almacenado (``purchase_order_line.py:84``), calculado sobre
las líneas que ya existen.

La columna guardaba ids de usuario. Se retira primero la FK, se traduce
cada id al contacto de su usuario y sólo entonces se crea la FK nueva: así
ninguna restricción ve un id del otro modelo."""
from django.db import migrations, models

from orm.migration_operations import ComputeStoredFields

UPDATE_ORDERS = """
UPDATE purchase_order po
SET partner_id = u.partner_id
FROM res_users u
WHERE po.partner_id = u.id
"""


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0115_rescompany_purchase_fields"),
        ("purchase", "0010_order_mixins"),
    ]

    operations = [
        migrations.AlterField(
            model_name="purchaseorder",
            name="partner_id",
            field=models.BigIntegerField(
                blank=True, null=True, db_column="partner_id"),
        ),
        migrations.RunSQL(UPDATE_ORDERS, migrations.RunSQL.noop),
        migrations.AlterField(
            model_name="purchaseorder",
            name="partner_id",
            field=models.ForeignKey(
                blank=True,
                db_column="partner_id",
                db_index=True,
                help_text=(
                    "You can find a vendor by its Name, TIN, Email or "
                    "Internal Reference."
                ),
                null=True,
                on_delete=models.PROTECT,
                related_name="purchase_orders",
                to="base.respartner",
                verbose_name="Vendor",
            ),
        ),
        migrations.AddField(
            model_name="purchaseorderline",
            name="partner_id",
            field=models.ForeignKey(
                blank=True,
                db_column="partner_id",
                editable=False,
                null=True,
                on_delete=models.SET_NULL,
                related_name="purchase_line_ids",
                to="base.respartner",
                verbose_name="Partner",
            ),
        ),
        # La línea gana un calculado almacenado: se calcula sobre las filas
        # que ya existen, como ``models.py:3220-3238`` de la fuente.
        ComputeStoredFields('purchase', 'purchaseorderline', [
            'partner_id',
        ]),
    ]
