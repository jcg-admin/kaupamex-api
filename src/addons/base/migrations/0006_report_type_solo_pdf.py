"""``report_type`` se reduce a lo que este árbol sabe emitir: ``pdf``.

La 0005 quitó el prefijo ``qweb-`` y dejó ``pdf``/``text``. El ``text`` venía
del catálogo de la referencia, no de una capacidad nuestra: medido, **0**
addons lo declaraban y **0** tests ejercitaban su renderizador — y su
renderizador exigía del ``builder`` un contrato distinto (``str`` en vez del
descriptor) que nada hacía cumplir. Es el mismo defecto que el prefijo, un
nivel más abajo: declarar como opción una capacidad ajena. Ver H-API-291 y
``REPORT_TYPE_CHOICES``.

**Sin conversión de filas, a propósito.** La 0005 sí convertía porque el valor
viejo tenía destino (``qweb-pdf`` → ``pdf``); aquí ``text`` no lo tiene: no hay
formato al que reasignarlo sin inventar un renderizador. Una fila que quedara
con ``text`` cae en el contrato de ausencia del motor y devuelve ``None`` —
visible, que es lo correcto. Medido: la tabla no tiene filas (ninguna
data-migration crea ``ir.actions.report``), así que el caso es hipotético.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0005_report_type_sin_prefijo_qweb"),
    ]

    operations = [
        migrations.AlterField(
            model_name="iractionsreport",
            name="report_type",
            field=models.CharField(
                choices=[("pdf", "PDF")],
                default="pdf",
                help_text="Formato de salida. Sólo los que este árbol sabe "
                          "emitir: hoy PDF, vía helper libharu (ADR-017). "
                          "Un formato nuevo entra con su renderizador.",
                max_length=16,
                verbose_name="Tipo de reporte",
            ),
        ),
    ]
