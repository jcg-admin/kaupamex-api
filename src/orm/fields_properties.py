"""Campos de propiedades dinámicas — fiel a ``odoo/orm/fields_properties.py``.

Odoo ``Properties``/``PropertiesDefinition`` = propiedades dinámicas por registro
(esquema definido en un padre). En Django el equivalente natural es
``JSONField`` (esquema validado en el serializer/clean). Alias de lectura.

``property_to_sql`` — extraer UNA propiedad del JSON
====================================================

``Field.property_to_sql`` (``orm/fields.py``) rechaza por defecto: sólo un
campo que contenga sub-campos sabe sacar uno. ``Properties`` es ese campo, y
allá lo sobreescribe (``odoo19c: odoo/orm/fields_properties.py:674-676``) con
tres líneas: valida el nombre y emite ``(campo -> 'nombre')``.

Aquí ``Properties`` **es** ``models.JSONField``, así que el método se adjunta a
esa clase — misma divergencia de forma que ``orm/fields.py`` declara para
``to_sql``: la clase es de Django y no es nuestra para declararla.

Consecuencia que conviene saber, y es una diferencia real con la fuente: allá
``Properties`` y ``Json`` son **clases distintas** y sólo la primera lo tiene;
aquí las dos son ``JSONField``, así que un ``fields.Json`` también responde a
``property_to_sql``. Es un ensanchamiento, no un defecto: el operador ``->``
de PostgreSQL funciona igual sobre cualquier ``jsonb``, y ``_field_to_sql``
sólo lo invoca cuando la expresión trae un punto.
"""
from django.db import models

from orm.utils import regex_alphanumeric
from tools.sql import SQL

__all__ = ['Properties', 'PropertiesDefinition', 'check_property_field_value_name']

Properties = models.JSONField
PropertiesDefinition = models.JSONField


def check_property_field_value_name(property_name):
    """≙ ``check_property_field_value_name`` (``odoo19c: :27-29``).

    El nombre de una propiedad va **interpolado en el SQL**, así que se acota
    antes: hasta 512 caracteres y sólo minúsculas, dígitos y guion bajo.
    """
    if not (0 < len(property_name) <= 512) or not regex_alphanumeric.match(property_name):
        raise ValueError(f"Wrong property field value name {property_name!r}.")


def _properties_property_to_sql(self, field_sql, property_name, model, alias, query):
    """``property_to_sql`` — ≙ ``Properties.property_to_sql`` (``:674-676``)."""
    check_property_field_value_name(property_name)
    return SQL("(%s -> %s)", field_sql, property_name)


models.JSONField.property_to_sql = _properties_property_to_sql
