"""``report_type`` pierde el prefijo ``qweb-`` de la referencia.

El valor nombraba un **par** (lenguaje de plantillas, formato) — ``qweb-pdf``.
Aquí no hay lenguaje de plantillas: el documento es código (un ``builder``), y
el JSON es el intermedio, no el intérprete. Queda sólo el formato de salida.
``qweb-html`` desaparece sin análogo: este árbol no emite HTML.

Razonamiento completo en ``REPORT_TYPE_CHOICES``
(``addons/base/models/ir_actions_report.py``).

La conversión de filas es **defensiva**. Medido antes del cambio: ningún
data-migration del árbol crea filas de ``ir.actions.report``, así que la tabla
no debería tener ninguna. Se convierte igual porque, si alguna existiera con
el valor viejo, el motor la despacharía sin acierto contra
``RENDERER_BY_TYPE`` y devolvería ``None`` — el contrato de ausencia taparía
el dato roto en vez de delatarlo. Seis líneas contra un fallo silencioso.
"""
from django.db import migrations, models

#: Valor viejo → nuevo. ``qweb-html`` no se mapea: no hay formato destino, y
#: una fila así queda fuera del enum — visible, que es lo correcto.
RENOMBRES = {'qweb-pdf': 'pdf', 'qweb-text': 'text'}


def quitar_prefijo(apps, schema_editor):
    IrActionsReport = apps.get_model('base', 'IrActionsReport')
    for viejo, nuevo in RENOMBRES.items():
        IrActionsReport.objects.filter(report_type=viejo).update(
            report_type=nuevo)


def restaurar_prefijo(apps, schema_editor):
    IrActionsReport = apps.get_model('base', 'IrActionsReport')
    for viejo, nuevo in RENOMBRES.items():
        IrActionsReport.objects.filter(report_type=nuevo).update(
            report_type=viejo)


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0004_resdevice"),
    ]

    operations = [
        migrations.AlterField(
            model_name="iractionsreport",
            name="report_type",
            field=models.CharField(
                choices=[("pdf", "PDF"), ("text", "Texto")],
                default="pdf",
                help_text="Formato de salida. Sin el prefijo qweb- de la "
                          "referencia: aquí no hay QWeb, el render es libharu "
                          "(ADR-017).",
                max_length=16,
                verbose_name="Tipo de reporte",
            ),
        ),
        migrations.RunPython(quitar_prefijo, restaurar_prefijo),
    ]
