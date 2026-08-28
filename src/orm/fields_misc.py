"""Campos misceláneos — fiel a ``odoo/orm/fields_misc.py`` (Odoo 19).

``Boolean``, ``Json`` (Odoo ``Id`` es el pk implícito: en Django lo provee
``AutoField``/``BigAutoField`` automático, no se declara).

``Boolean`` es un **despachador** de ``company_dependent`` (tarea #129), no un
alias pelado: el tipo está en ``COMPANY_DEPENDENT_FIELDS`` y tiene cuatro
consumidores en la referencia — ``account/models/partner.py:573-574``
(``ignore_abnormal_invoice_date`` / ``_amount``),
``purchase/models/res_partner.py:41`` (``receipt_reminder_email``) y
``sale_purchase/models/product_template.py:11`` (``service_to_purchase``).

``Json`` **no** lo lleva: ``json`` no está en la lista cerrada de tipos de la
fuente (``odoo19c: odoo/orm/fields.py:42-44``), y además un campo por empresa
YA es un ``jsonb`` — anidarlo no tendría dónde poner el mapa de empresas.
"""
from django.db import models

from orm.fields_company_dependent import make_dispatcher

__all__ = ['Boolean', 'Json']

Boolean = make_dispatcher('Boolean', 'boolean', models.BooleanField)
Json = models.JSONField
