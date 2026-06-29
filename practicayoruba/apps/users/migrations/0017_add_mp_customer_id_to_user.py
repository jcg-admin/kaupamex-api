from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0016_add_recibo_pdf_generado_action"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="mp_customer_id",
            field=models.CharField(
                blank=True,
                default="",
                help_text="ID del customer en MP para guardar tarjetas. BR-009.",
                max_length=100,
                verbose_name="ID cliente MercadoPago",
            ),
        ),
    ]
