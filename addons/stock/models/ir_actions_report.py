r"""``ir.actions.report`` — el contexto de la etiqueta de recepción: NO PORTADO.

Adaptación de Odoo ``stock/models/ir_actions_report.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 16 líneas) — atribución y aviso
de licencia preservados (DEC-KX-03). El archivo entero de la referencia:

.. code-block:: python

    class IrActionsReport(models.Model):
        _inherit = 'ir.actions.report'

        def _get_rendering_context(self, report, docids, data):
            data = super()._get_rendering_context(report, docids, data)
            if report.report_name == 'stock.report_reception_report_label' and not docids:
                docids = data['docids']
                docs = self.env[report.model].browse(docids)
                data.update({
                    'doc_ids': docids,
                    'docs': docs,
                })
            return data

Un solo símbolo, y es un **parche de un caso**: la etiqueta del informe de
recepción se imprime sin ``docids`` en la llamada, con los identificadores
metidos dentro de ``data``. El método los rescata de ahí y repone las dos claves
que la plantilla espera.

Por qué NO se porta — medido, no supuesto
==========================================

Extiende ``_get_rendering_context``, que **no existe** en nuestro
``IrActionsReport``:

.. code-block:: text

    grep -rn "def _get_rendering_context" src/ addons/ --include=*.py → 0

[PROVEN, medido en el pase que escribe este archivo.]

Y su ausencia no es un olvido: ``_get_rendering_context`` es el punto donde el
motor **QWeb** de la referencia arma el diccionario que la plantilla consume, y
ese motor no está portado. Nuestro ``IrActionsReport``
(``src/addons/base/models/ir_actions_report.py:305``) declara otra superficie —
``render``, ``_render_pdf``, ``_descriptor_from_view`` — sobre el motor PDF
propio (ADR-017, libharu).

Portar el parche sin el método que parchea daría un símbolo que nada encadena:
el "relleno" que ``auto-audit-before-writing.md`` prohíbe.

Dónde vive de verdad el bloqueo
================================

Dos capas por debajo, y las dos ya tienen dueño:

1. **El informe no existe.** ``stock.report_reception_report_label`` es un
   ``ReportSpec`` que ``stock`` debería declarar y no declara — ya registrado
   como tarea **#279** (*"stock no declara ningún ReportSpec propio"*).
2. **El motor de plantillas es otro.** Mientras el renderizado no pase por
   QWeb, no hay un ``_get_rendering_context`` que extender; el equivalente
   nuestro es el descriptor que ``_descriptor_from_view`` construye.

Cuando **#279** declare el informe, la pregunta correcta no será *"¿cómo porto
este método?"* sino *"¿qué le falta al descriptor de esa etiqueta?"* — y la
respuesta se escribirá contra nuestro motor, no contra QWeb.

Sucesor
========

Tarea **#279** (el ``ReportSpec`` de ``stock``) es la precondición; este archivo
se completa —o se cierra como divergencia de mecanismo declarada— en ese mismo
pase. La decisión de forma es de ahí, no de aquí.
"""
