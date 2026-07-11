"""Canon-idioma (DEC canon-idioma-enums-error-codes): el value de la accion de
BusinessEvent estaba en espanol (``RECIBO_PDF_GENERADO``) mientras las otras 14
acciones estan en ingles (``ORDER_CREATED``, ``STOCK_ADJUSTED_TO_ZERO``, ...).
Los values de choices son constantes -> canon ingles. Se renombra a
``RECEIPT_PDF_GENERATED`` y se migran las filas existentes (data-fix, reversible).

El guard append-only de BusinessEvent es a nivel de instancia (save/delete); el
modelo historico que reconstruye la migracion es plano (sin ese guard) y
``QuerySet.update()`` no invoca save(), asi que el rename bulk es seguro y no
altera la semantica del evento (mismo hecho, value canonico).
"""
from django.db import migrations, models


OLD = "RECIBO_PDF_GENERADO"
NEW = "RECEIPT_PDF_GENERATED"


def rename_forward(apps, schema_editor):
    BusinessEvent = apps.get_model("users", "BusinessEvent")
    BusinessEvent.objects.filter(action=OLD).update(action=NEW)


def rename_backward(apps, schema_editor):
    BusinessEvent = apps.get_model("users", "BusinessEvent")
    BusinessEvent.objects.filter(action=NEW).update(action=OLD)


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0019_businessevent_correlation_id"),
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
                    ("RECEIPT_PDF_GENERATED",  "Receipt PDF generado"),
                ],
                db_index=True,
                max_length=30,
            ),
        ),
        migrations.RunPython(rename_forward, rename_backward),
    ]
