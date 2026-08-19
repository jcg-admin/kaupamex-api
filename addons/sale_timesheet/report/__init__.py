"""Informes del addon ``sale_timesheet`` (estructura Odoo: ``report/``, dos
archivos, los dos de la referencia).

**No importa ningún modelo** — los dos archivos extienden informes SQL cuyo
modelo base no existe en este árbol (``timesheets.analysis.report`` es de
``hr_timesheet``; ``report.project.task.user`` es de ``project``), así que los
dos son no-op declarado. Sus funciones ``apply_*_extensions`` las invoca
``SaleTimesheetConfig.ready()``, no este paquete: son el punto de cableado
para el día que los informes base aterricen.

Ver el desenlace medido, símbolo por símbolo, en el docstring de cada archivo.
"""
