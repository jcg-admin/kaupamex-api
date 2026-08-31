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
from orm.fields_nonstored import (
    _UNSET,
    NonStored,
    annotate_related,
    projection_or_none,
)

__all__ = ['Boolean', 'Json']

Boolean = make_dispatcher('Boolean', 'boolean', models.BooleanField)
def Json(*args, store=_UNSET, related=None, **kwargs):
    """``fields.Json`` — el ``JSONField`` de Django, con y sin columna.

    Era un alias pelado (``Json = models.JSONField``) y pasa a ser despachador
    por un solo motivo medido: la referencia declara ``fields.Json(related=…)``
    y el alias no tenía dónde recibir la clave — el conteo lo publica
    ``python3 scripts/census_related_fields.py``.

    **No usa** :func:`~orm.fields_company_dependent.make_dispatcher`, que es
    el camino de los otros: su fábrica valida el tipo base contra los diez que
    la referencia declara ``company_dependent``, y ``json`` no está entre
    ellos. Forzarlo ahí habría exigido ensanchar esa lista para un caso que la
    fuente no tiene, que es construir de más.

    Nadie hace ``isinstance(campo, fields.Json)`` en este árbol —medido—, así
    que ser función no rompe ninguna identidad de tipo. Si algún día hiciera
    falta, la salida es un ``__new__`` como el de ``Html``.
    """
    if store is not _UNSET:
        kwargs['store'] = store
    projection, related_attrs = projection_or_none(related, kwargs)
    if projection is not None:
        return projection
    if not related_attrs['store']:
        field = NonStored(*args, **kwargs)
    else:
        field = models.JSONField(*args, **kwargs)
    return annotate_related(field, related, related_attrs)
