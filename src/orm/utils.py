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

from django.db import models

from exceptions import ValidationError
from orm.fields_nonstored import non_stored_fields

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


def record_ids(records):
    """Los ids de ``records`` — la adaptación de ``BaseModel._ids``.

    La fuente pasa por todas partes un *recordset*, que es un objeto con
    ``_ids``: una tupla de ids del mismo modelo. Aquí no hay recordset —un
    conjunto de filas es una instancia de modelo de Django, un ``QuerySet``, o
    un iterable de cualquiera de los dos— así que el atributo no existe y la
    firma de la fuente no se puede portar literal.

    Ésta es la traducción, y es de **mecanismo**, no de alcance: donde la
    fuente escribe ``records._ids``, aquí se escribe ``record_ids(records)`` y
    el resto del cuerpo queda igual. Acepta las cuatro formas que el árbol
    produce:

    - una instancia de modelo → su ``pk`` (``None`` incluido: un registro sin
      guardar tiene id falsy, que es lo que la fuente llama *nuevo*);
    - un ``QuerySet`` → los ``pk`` de sus filas, en una sola consulta;
    - un iterable de instancias o de enteros;
    - ``None`` → vacío.

    Devuelve siempre una **tupla**, como ``_ids`` en la fuente: el llamador la
    recorre más de una vez (``_update_cache`` la usa dos veces seguidas) y un
    generador se agotaría en la primera.
    """
    if records is None:
        return ()
    if isinstance(records, models.Model):
        return (records.pk,)
    if isinstance(records, models.QuerySet):
        return tuple(records.values_list('pk', flat=True))
    return tuple(
        item.pk if isinstance(item, models.Model) else item
        for item in records
    )


def model_field_registry(model):
    """El mapa ``nombre -> campo`` de una clase de modelo.

    Es el cuerpo de ``BaseModel._fields`` sacado a funcion para que se pueda
    consultar **sobre la clase**, no solo sobre una instancia. La fuente lo
    tiene asi de nacimiento: su ``Model._fields`` es un atributo de la clase de
    registro, y ``resolve_depends`` lo recorre sin instanciar nada
    (``odoo19c: odoo/orm/fields.py:823``). Aqui ``_fields`` es una ``property``
    del modelo base, asi que sobre la clase devuelve el objeto ``property`` y
    no el mapa.

    Antes de esto ``resolve_depends`` resolvia con ``_meta.get_field``, que es
    **mas estrecho**: un :class:`~orm.fields_nonstored.NonStored` no tiene
    columna y por tanto no esta en ``_meta``. Esa es exactamente la ceguera que
    :ref:`h-api-1025` ya habia corregido en ``_fields`` y que este camino
    seguia teniendo — un ``@api.depends`` sobre un campo sin columna no
    resolvia, y el silencio se leia como «esa dependencia no existe».

    Un solo cuerpo para los dos consumidores: duplicar la construccion seria la
    segunda fuente de verdad que ``calibration-verified-numbers.md`` prohibe, y
    aqui divergiria justo por el eje que ya fallo una vez.
    """
    registry = {field.name: field for field in model._meta.get_fields()}
    registry.update(non_stored_fields(model))
    return registry
