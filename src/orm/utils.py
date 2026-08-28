"""Utilidades del ORM — fiel a ``odoo/orm/utils.py`` (Odoo 19).

Constantes y validadores puros del ORM. Las constantes (``SUPERUSER_ID``,
``COLLECTION_TYPES``, granularidades de ``read_group``) y los validadores de
nombre (``check_object_name``, ``check_pg_name``, ``parse_field_expr``) son
**puro Python, sin dependencia del motor**, así que se portan fieles.

``SUPERUSER_ID = 1`` es el id hard-coded del super-usuario (root / OdooBot); en
Django el equivalente es ``is_superuser`` en el modelo de usuario, pero el **id**
1 se preserva como constante fiel para paridad con seeds y referencias Odoo.

Se **omite** ``SQL_OPERATORS`` de Odoo: es plumbing del query-builder de Odoo
(mapea operador → fragmento SQL concatenable de ``odoo.tools.SQL``). Aquí el
compilador de queries es el ORM de Django (``QuerySet``/``Q``, ≙ ``orm/domains``),
que construye el SQL nativo — no se concatenan fragmentos a mano. Portar el dict
sobre ``RawSQL`` (que exige ``params`` y no es un fragmento concatenable) daría un
objeto inservible; misma razón que los stubs de motor (environments/registry).
"""
import re
from collections.abc import Set as AbstractSet

from exceptions import ValidationError

regex_object_name = re.compile(r'^[a-z0-9_.]+$')
regex_pg_name = re.compile(r'^[a-z_][a-z0-9_$]*$', re.IGNORECASE)

# tipos tratados como colecciones (fiel a Odoo 19)
COLLECTION_TYPES = (list, tuple, AbstractSet)
# id hard-coded del super-usuario (root / OdooBot). En Django la autoridad es
# ``is_superuser``; el id 1 se preserva para paridad con seeds/refs Odoo.
SUPERUSER_ID = 1

# granularidades de ``_read_group`` — fiel a Odoo 19 (nombres → token SQL).
READ_GROUP_NUMBER_GRANULARITY = {
    'year_number': 'year',
    'quarter_number': 'quarter',
    'month_number': 'month',
    'iso_week_number': 'week',
    'day_of_year': 'doy',
    'day_of_month': 'day',
    'day_of_week': 'dow',
    'hour_number': 'hour',
    'minute_number': 'minute',
    'second_number': 'second',
}


def check_object_name(name):
    """``True`` si ``name`` es un nombre de modelo válido (minúsculas,
    dígitos, ``_`` y ``.``). Fiel a Odoo 19."""
    return regex_object_name.match(name) is not None


def check_pg_name(name):
    """Valida que ``name`` sea un identificador PostgreSQL/SQL válido.

    Fiel a Odoo 19 (levanta ``ValidationError``, no ``ValueError``): caracteres
    permitidos + longitud ≤ 63. En Django el ORM ya valida nombres de
    columna/tabla al construir el schema; se preserva para paridad cuando un
    addon compone SQL crudo vía ``tools/sql.py``.
    """
    if not regex_pg_name.match(name):
        raise ValidationError("Invalid characters in table name %r" % name)
    if len(name) > 63:
        raise ValidationError("Table name %r is too long" % name)


#: ≙ ``regex_alphanumeric`` (``odoo19c: odoo/orm/utils.py:10``). Acota el
#: nombre de una propiedad, que va interpolado en el SQL.
regex_alphanumeric = re.compile(r'^[a-z0-9_]+$')


def parse_field_expr(field_expr: str) -> tuple[str, str | None]:
    """Separa ``field.property`` en ``(field, property|None)``. Fiel a Odoo 19."""
    if (property_index := field_expr.find(".")) >= 0:
        property_name = field_expr[property_index + 1:]
        field_expr = field_expr[:property_index]
    else:
        property_name = None
    if not field_expr:
        raise ValueError(f"Invalid field expression {field_expr!r}")
    return field_expr, property_name


def expand_ids(id0, ids):
    """Itera ids únicos de ``[id0] + ids`` del mismo tipo (todos reales o todos
    nuevos). Fiel a Odoo 19."""
    yield id0
    seen = {id0}
    kind = bool(id0)
    for id_ in ids:
        if id_ not in seen and bool(id_) == kind:
            yield id_
            seen.add(id_)
