"""Campos textuales — fiel a ``odoo/orm/fields_textual.py`` (Odoo 19).

``Char`` y ``Text`` (Odoo también ``Html``: ≈ ``TextField`` + saneo con
``dompurify`` en UI; se expone como alias de ``TextField``). Alias de nombre
Odoo → clase Django (firma Django).

``store=False`` — el campo sin columna
=======================================

En la referencia un campo puede declararse sin persistencia:
``fields.Char(store=False, default=_get_algo)``
(``odoo19c: account/models/res_currency.py:17``). Django no lo tiene: todo
``models.Field`` es una columna.

Por eso ``Char`` no es un alias pelado sino un **despachador**: con ``store``
por defecto devuelve el ``CharField`` de siempre, y con ``store=False``
devuelve un :class:`~orm.fields_nonstored.NonStored`. El sitio de declaración
queda **idéntico al de la fuente**, que es el punto — la alternativa era
repartir en el cableado de cada addon lo que la referencia declara en la clase.

``Text`` y ``Html`` siguen siendo alias directos: ``grep -rn
"Text(store=False\\|Html(store=False)"`` sobre ``odoo19c:`` da **0** — la
referencia no declara ninguno sin almacenar, así que darles el despachador
sería construir para un caso que no existe.
"""
from django.db import models

from orm.fields_nonstored import NonStored

__all__ = ['Char', 'Text', 'Html']

Text = models.TextField
Html = models.TextField               # Odoo Html ≈ TextField (saneo en capa UI)


def Char(*args, store=True, **kwargs):
    """``fields.Char`` — ≙ el de la referencia, con y sin columna.

    ``store=True`` (el defecto, y el de los 432 usos del árbol) devuelve un
    ``models.CharField`` con la firma de Django, exactamente como antes.

    ``store=False`` devuelve un campo **no persistido** cuyo valor sale de
    ``default`` al leerlo. No genera migración ni aparece en ``_meta``, que es
    lo que la referencia promete con esa bandera.
    """
    if store:
        return models.CharField(*args, **kwargs)
    return NonStored(*args, **kwargs)
