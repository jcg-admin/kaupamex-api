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
fuente son ``compute`` no almacenados). ``Integer`` y ``Float`` siguen siendo
alias pelados: 0 usos con ``store=False`` en el árbol al escribir esto.
"""
from django.db import models

from orm.fields_nonstored import NonStored

__all__ = ['Integer', 'Float', 'Monetary']

Integer = models.IntegerField
Float = models.FloatField


def Monetary(*args, store=True, help=None, **kwargs):
    """``fields.Monetary`` — ≙ el de la referencia, con y sin columna.

    ``help=`` es el alias de firma de la fuente para ``help_text=`` (misma
    tabla de alias que ``Char``).
    """
    if help is not None:
        kwargs.setdefault('help_text', help)
    if not store:
        return NonStored(*args, **kwargs)
    return models.DecimalField(*args, **kwargs)
