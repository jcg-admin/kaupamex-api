from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0015_add_stock_adjusted_to_zero_action"),
    ]

    operations = [
        migrations.AlterField(
            model_name="businessevent",
            name="action",
            field=models.CharField(
                choices=[
                    ("ORDER_CREATED",          "Order creada"),
                    ("ORDER_CANCELLED",        "Order cancelada"),
                    ("RETURN_REQUESTED",       "Return solicitada"),
                    ("RETURN_RESOLVED",        "Return resuelta"),
                    ("STOCK_ADJUSTED_TO_ZERO", "Stock ajustado a cero"),
                    ("RECIBO_PDF_GENERADO",    "Recibo PDF generado"),
                ],
                db_index=True,
                max_length=30,
            ),
        ),
    ]
