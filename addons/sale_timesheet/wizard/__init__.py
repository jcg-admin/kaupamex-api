"""Asistentes del addon ``sale_timesheet`` (estructura Odoo: ``wizard/``, un
archivo, el de la referencia).

**No importa ningún modelo** — ``sale_make_invoice_advance.py`` extiende
``sale.advance.payment.inv``, asistente que declara ``sale`` y que este árbol
no tiene (``addons/sale/`` no tiene directorio ``wizard/``), así que es no-op
declarado. Su función ``apply_*_extensions`` la invoca
``SaleTimesheetConfig.ready()``.

Ver el desenlace medido, símbolo por símbolo, en el docstring del archivo.
"""
