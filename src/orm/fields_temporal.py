"""Campos temporales — fiel a ``odoo/orm/fields_temporal.py`` (Odoo 19).

``Date`` y ``Datetime``, los dos como **despachadores** de
``company_dependent`` (tarea #129) y no como alias pelados: los dos tipos
están en ``COMPANY_DEPENDENT_FIELDS``
(``odoo19c: odoo/orm/fields.py:42-44``).

Sus consumidores en la fuente están en el addon de prueba
(``odoo/addons/test_orm/models/test_orm.py:725-726``), no en código de
producto. Se cablean igual porque la lista de tipos admitidos es de la fuente:
que hoy sólo la ejerciten sus propias pruebas no la acorta — el mismo criterio
con que ``COMPANY_DEPENDENT_FIELDS`` se copió entera y no filtrada.
"""
from django.db import models

from orm.fields_company_dependent import make_dispatcher

__all__ = ['Date', 'Datetime']

Date = make_dispatcher('Date', 'date', models.DateField)
Datetime = make_dispatcher('Datetime', 'datetime', models.DateTimeField)
