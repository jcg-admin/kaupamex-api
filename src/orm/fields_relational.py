"""Campos relacionales — fiel a ``odoo/orm/fields_relational.py`` (Odoo 19).

``Many2one`` = ``ForeignKey``; ``Many2many`` = ``ManyToManyField``; ``One2many``
es el reverso de un FK en Django (``related_name``), sin clase propia.

``store=False`` — el Many2one sin columna
==========================================

La referencia declara relaciones **calculadas y no almacenadas**::

    properties_base_definition_id = fields.Many2one(
        "properties.base.definition",
        compute="_compute_properties_base_definition_id",
        search="_search_properties_base_definition_id",
    )

(``odoo19c: odoo/addons/base/models/properties_base_definition_mixin.py:21-25``)
— un ``compute`` sin ``store`` **no tiene columna**: el valor se resuelve al
leerlo. Django no lo tiene: todo ``ForeignKey`` es una columna.

Por eso ``Many2one`` deja de ser un alias pelado y pasa a ser un
**despachador**, el mismo patrón que ya tienen ``Char``
(``orm/fields_textual.py``) y ``Float`` (``orm/fields_numeric.py``): con
``store`` por defecto devuelve el ``ForeignKey`` de siempre y con
``store=False`` devuelve un :class:`~orm.fields_nonstored.NonStored`. El sitio
de declaración queda **idéntico al de la fuente**, que es el punto — la
alternativa era colgar una ``property`` fuera de la clase y repartir en el
cableado lo que la referencia declara en el cuerpo.

``join`` — el salto de un camino relacional
===========================================

``Many2one.join`` (``odoo19c: odoo/orm/fields_relational.py:466``) añade a una
consulta el LEFT JOIN que sigue este campo y devuelve el par
``(comodelo, alias)``. Lo consume ``BaseModel._traverse_related_sql``, que
recorre un campo delegado salto a salto.

Se adjunta a ``models.ForeignKey`` —la clase que ``Many2one`` devuelve— por la
misma razón de forma que ``orm/fields.py`` declara para ``to_sql``: la clase es
de Django y no es nuestra para declararla. Medido antes de adjuntar: ``join``
da ``False`` en ``hasattr(models.ForeignKey, 'join')``.

``Many2many`` **no** lleva el despachador: ``grep -rn "Many2many(" ``
sobre ``odoo19c:`` no arroja ninguna declarada ``store=False`` con ``compute``
sin almacenar en la familia ``base``, así que dárselo sería construir para un
caso que no existe.
"""
from django.db import models

from orm.fields_nonstored import NonStored
from tools.sql import SQL

__all__ = ['Many2one', 'One2many', 'Many2many']

One2many = None                       # reverso de FK (related_name)
Many2many = models.ManyToManyField


def Many2one(*args, store=True, **kwargs):
    """``fields.Many2one`` — ≙ el de la referencia, con y sin columna.

    ``store=True`` (el defecto, y el de todos los usos previos del árbol)
    devuelve un ``models.ForeignKey`` con la firma de Django, exactamente como
    antes: el alias sigue siendo transparente para quien no nombra ``store``.

    ``store=False`` devuelve un campo **no persistido** cuyo valor sale de
    ``default`` al leerlo. No genera migración ni aparece en ``_meta``, que es
    lo que la referencia promete con un ``compute`` sin ``store``. El primer
    argumento posicional —el modelo apuntado— se acepta y se descarta, igual
    que ``NonStored`` descarta el resto de la firma de Django.
    """
    if store:
        return models.ForeignKey(*args, **kwargs)
    return NonStored(*args, **kwargs)


def _many2one_join(self, model, alias, query):
    """``join`` — añade el LEFT JOIN de este Many2one y devuelve (modelo, alias).

    ≙ ``Many2one.join`` (``odoo19c: odoo/orm/fields_relational.py:466-478``).
    Es lo que ``BaseModel._traverse_related_sql`` invoca en cada salto de un
    camino relacional: sin él, un campo delegado no se puede resolver a SQL.

    La condición ON se compone con ``model._field_to_sql(alias, self.name,
    query)`` —el mismo punto de entrada que la fuente usa— para que la columna
    del lado izquierdo salga del mismo sitio que cualquier otra, con su
    comprobación de acceso incluida.

    Divergencias de nombre, las dos mecánicas: el comodelo se obtiene de
    ``self.related_model`` en vez de ``model.env[self.comodel_name]`` —Django
    ya lo tiene resuelto en el campo—, y su tabla de ``_meta.db_table`` en vez
    de ``_table``.
    """
    comodel = self.related_model
    coalias = query.make_alias(alias, self.name)
    query.add_join('LEFT JOIN', coalias, comodel._meta.db_table, SQL(
        "%s = %s",
        model._field_to_sql(alias, self.name, query),
        SQL.identifier(coalias, 'id'),
    ))
    return (comodel, coalias)


models.ForeignKey.join = _many2one_join
