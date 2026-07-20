"""
Models — addons.reports.

El addon ``reports`` es un **paquete controlador delgado** del framework de
reportes: agrega (``aggregations.py``), renderiza PDF (``pdf_report.py``) y
sirve los endpoints (``views.py``) sobre tablas existentes, todas de solo
lectura. **No tiene modelos propios.**

El único modelo persistente era ``ExportJob`` (estado del export asíncrono,
rama ``rows>5000`` de UC-REP-05). Se movió a su hogar fiel ``addons.base``
(``base/models/report_export_job.py``): en Odoo el framework de reportes
(``ir.actions.report`` + QWeb) vive en ``base``/``web``, no en un módulo
``reports`` separado. Los consumidores importan ``ExportJob`` desde
``addons.base.models``.
"""
