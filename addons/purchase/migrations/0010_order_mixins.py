"""Las columnas de ``portal.mixin`` y ``analytic.mixin`` que heredan la
orden y la línea (``odoo19c: purchase_order.py:23``;
``purchase_order_line.py:15``)."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("purchase", "0009_order_header"),
    ]

    operations = [
        migrations.AddField(
            model_name="purchaseorder",
            name="access_token",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                help_text=(
                    "Token que permite el acceso al documento por link, "
                    "saltando los permisos del destinatario (Odoo "
                    "access_token)."
                ),
                max_length=64,
                verbose_name="Token de seguridad",
            ),
        ),
        migrations.AddField(
            model_name="purchaseorderline",
            name="analytic_distribution",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text=(
                    'Odoo analytic_distribution: {"id1,id2,...": '
                    'porcentaje}.'
                ),
                null=True,
                verbose_name="Distribución analítica",
            ),
        ),
    ]
