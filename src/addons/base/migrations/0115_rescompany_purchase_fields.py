"""Lo que ``purchase`` cuelga en ``res.company``: ``po_lock``,
``po_double_validation`` y ``po_double_validation_amount``
(``odoo19c: addons/purchase/models/res_company.py:10-23``)."""

from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0114_res_partner_category_partner_ids"),
    ]

    operations = [
        migrations.AddField(
            model_name="rescompany",
            name="po_double_validation",
            field=models.CharField(
                choices=[
                    ("one_step", "Confirm purchase orders in one step"),
                    (
                        "two_step",
                        "Get 2 levels of approvals to confirm a purchase "
                        "order",
                    ),
                ],
                default="one_step",
                help_text=(
                    "Provide a double validation mechanism for purchases"),
                max_length=8,
                verbose_name="Levels of Approvals",
            ),
        ),
        migrations.AddField(
            model_name="rescompany",
            name="po_double_validation_amount",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("5000"),
                help_text=(
                    "Minimum amount for which a double validation is "
                    "required"),
                max_digits=16,
                verbose_name="Double validation amount",
            ),
        ),
        migrations.AddField(
            model_name="rescompany",
            name="po_lock",
            field=models.CharField(
                choices=[
                    ("edit", "Allow to edit purchase orders"),
                    ("lock", "Confirmed purchase orders are not editable"),
                ],
                default="edit",
                help_text=(
                    "Purchase Order Modification used when you want to "
                    "purchase order editable after confirm"),
                max_length=4,
                verbose_name="Purchase Order Modification",
            ),
        ),
    ]
