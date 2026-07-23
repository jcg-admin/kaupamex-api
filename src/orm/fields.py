"""Campos del ORM — agregador, fiel a ``odoo/orm/fields.py`` (Odoo 19).

En Odoo 19 los campos se definen por **categoría** en
``odoo/orm/fields_{textual,numeric,temporal,selection,relational,binary,misc,
reference,properties}.py`` y se agregan hacia la superficie pública. Aquí se
replica el split (monolito modular: un archivo por categoría) y este módulo los
**agrega**; ``src/fields/__init__.py`` (≙ ``odoo/fields/__init__.py``) re-exporta
de aquí + ``Command``.

Cada nombre mapea el *nombre* de campo de Odoo → la clase de Django; la *firma*
difiere (alias de lectura con parámetros Django).
"""
from orm.fields_binary import Binary, Image                    # noqa: F401
from orm.fields_misc import Boolean, Json                      # noqa: F401
from orm.fields_numeric import Float, Integer, Monetary        # noqa: F401
from orm.fields_properties import (                            # noqa: F401
    Properties,
    PropertiesDefinition,
)
from orm.fields_reference import Many2oneReference, Reference  # noqa: F401
from orm.fields_relational import Many2many, Many2one, One2many  # noqa: F401
from orm.fields_selection import Selection                     # noqa: F401
from orm.fields_temporal import Date, Datetime                 # noqa: F401
from orm.fields_textual import Char, Html, Text                # noqa: F401

__all__ = [
    'Char', 'Text', 'Html', 'Integer', 'Float', 'Monetary', 'Date', 'Datetime',
    'Selection', 'Many2one', 'One2many', 'Many2many', 'Binary', 'Image',
    'Boolean', 'Json', 'Reference', 'Many2oneReference', 'Properties',
    'PropertiesDefinition',
]
