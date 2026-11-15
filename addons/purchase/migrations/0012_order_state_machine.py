# ≙ purchase.order state, date_approve, locked, user_id; la línea
# display_type, is_downpayment (odoo19c: purchase_order.py:90,105-117,
# 157-159; purchase_order_line.py:91-95).

import addons.purchase.models.purchase_order
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("purchase", "0011_order_partner_is_contact"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="purchaseorder",
            name="date_approve",
            field=models.DateTimeField(
                blank=True, db_index=True, null=True,
                verbose_name="Confirmation Date"
            ),
        ),
        migrations.AddField(
            model_name="purchaseorder",
            name="locked",
            field=models.BooleanField(
                default=False,
                help_text="Locked Purchase Orders cannot be modified."
            ),
        ),
        migrations.AddField(
            model_name="purchaseorder",
            name="user_id",
            field=models.ForeignKey(
                blank=True,
                db_column="user_id",
                default=addons.purchase.models.purchase_order._default_buyer,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="purchase_orders_as_buyer",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Buyer",
            ),
        ),
        migrations.AddField(
            model_name="purchaseorderline",
            name="display_type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("line_section", "Section"),
                    ("line_subsection", "Subsection"),
                    ("line_note", "Note"),
                ],
                help_text="Technical field for UX purpose.",
                max_length=16,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="purchaseorderline",
            name="is_downpayment",
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name="purchaseorder",
            name="state",
            field=models.CharField(
                choices=[
                    ("draft", "Solicitud de cotización"),
                    ("sent", "Cotización enviada"),
                    ("to approve", "Por aprobar"),
                    ("purchase", "Orden de compra"),
                    ("cancel", "Cancelada"),
                ],
                db_index=True,
                default="draft",
                help_text="Estado (Odoo purchase.order.state).",
                max_length=16,
            ),
        ),
    ]
