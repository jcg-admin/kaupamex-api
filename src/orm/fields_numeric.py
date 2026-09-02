"""Campos numéricos — fiel a ``odoo/orm/fields_numeric.py`` (Odoo 19).

``Integer``, ``Float``, ``Monetary`` (Odoo Monetary = importe con moneda; alias
de ``DecimalField`` que en el proyecto sale como string por
``COERCE_DECIMAL_TO_STRING``).

``Monetary`` no es un alias pelado sino un **despachador** de ``store=``, igual
que ``Char`` (ver ``fields_textual.py``): con ``store=True`` (el defecto)
devuelve el ``DecimalField`` de siempre; con ``store=False`` devuelve un
:class:`~orm.fields_nonstored.NonStored` — la traducción fijada del campo
``compute`` sin columna de la referencia (precedente:
``account/models/account_analytic_distribution_model.py``, campo
``prefix_placeholder``). Primer consumidor Monetary:
``account/models/digest.py`` (los KPI ``kpi_account_*_value``, que en la
fuente son ``compute`` no almacenados). ``Integer`` y ``Float`` **no** llevan
la rama de ``store`` **propia**: la llevan por el molde de
:func:`~orm.fields_company_dependent.make_dispatcher`, que devuelve un
``NonStored`` en cuanto el ``store`` resuelto es falso — con ``related=``
o sin él. Primer consumidor de ``Integer(store=False)``:
``hr_recruitment/models/digest.py`` (tarea #159), cuyo KPI la fuente
declara ``fields.Integer(compute=…)``, sin columna.

``company_dependent`` — ``Integer`` y ``Float`` sí lo llevan (tarea #129)
=========================================================================

Los dos están en ``COMPANY_DEPENDENT_FIELDS``, y los dos tienen consumidor en
la referencia: ``purchase/models/res_partner.py:43``
(``reminder_date_before_receipt``, ``Integer``) y
``product/models/product_product.py:62`` (``standard_price``, ``Float``). Por
eso dejan de ser alias pelados y pasan a ser despachadores fabricados con
:func:`~orm.fields_company_dependent.make_dispatcher`.

``Monetary`` **no** lo lleva, y no por olvido: ``monetary`` no está en la lista
cerrada de tipos que la fuente admite
(``odoo19c: odoo/orm/fields.py:42-44``). El ``standard_price`` que aquí es
``Monetary`` y allá es ``Float`` company_dependent es una decisión propia —
tarea **#135**.
"""
from django.db import models

from orm.fields_company_dependent import make_dispatcher
from orm.fields_nonstored import (
    _UNSET,
    NonStored,
    annotate_related,
    projection_or_none,
)

__all__ = ['Integer', 'Float', 'Monetary']

Integer = make_dispatcher('Integer', 'integer', models.IntegerField)
Float = make_dispatcher('Float', 'float', models.FloatField)


def Monetary(*args, store=_UNSET, help=None, related=None, **kwargs):
    """``fields.Monetary`` — ≙ el de la referencia, con y sin columna.

    ``help=`` es el alias de firma de la fuente para ``help_text=`` (misma
    tabla de alias que ``Char``).
    """
    if help is not None:
        kwargs.setdefault('help_text', help)
    #: ``:452-458`` — el centinela, por el mismo motivo que en ``Char``: el
    #: defecto de ``store`` depende de si hay ``related``.
    if store is not _UNSET:
        kwargs['store'] = store
    projection, related_attrs = projection_or_none(related, kwargs)
    if projection is not None:
        return projection
    if not related_attrs['store']:
        field = NonStored(*args, **kwargs)
    else:
        field = models.DecimalField(*args, **kwargs)
    return annotate_related(field, related, related_attrs)
