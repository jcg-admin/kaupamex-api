# ≙ product.template purchase_method y purchase_line_warn_msg, que cuelga
# purchase (odoo19c: purchase/models/product.py:14-20); las plantillas
# existentes reciben su política de control del tipo de producto.

from django.db import migrations, models

from orm.migration_operations import ComputeStoredFields


class Migration(migrations.Migration):

    dependencies = [
        ("product", "0021_log_access_user_column_names"),
    ]

    operations = [
        migrations.AddField(
            model_name="producttemplate",
            name="purchase_line_warn_msg",
            field=models.TextField(
                blank=True, null=True,
                verbose_name="Message for Purchase Order Line"
            ),
        ),
        migrations.AddField(
            model_name="producttemplate",
            name="purchase_method",
            field=models.CharField(
                choices=[
                    ("purchase", "On ordered quantities"),
                    ("receive", "On received quantities"),
                ],
                default="receive",
                help_text=(
                    "On ordered quantities: Control bills based on ordered "
                    "quantities.\nOn received quantities: Control bills "
                    "based on received quantities."),
                max_length=8,
                verbose_name="Control Policy",
            ),
        ),
        ComputeStoredFields('product', 'producttemplate', ['purchase_method']),
    ]
