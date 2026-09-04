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
import warnings
from collections.abc import Set as AbstractSet

from django.db import models

from exceptions import AccessError, ValidationError
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


#: ≙ ``regex_private`` (``odoo19c: odoo/orm/utils.py:14``). El nombre reservado
#: del despacho remoto: el prefijo de guion bajo **y** ``init``, que no lo lleva
#: y es igual de interno.
regex_private = re.compile(r'^(_.*|init)$')


def check_method_name(name):
    """Levanta ``AccessError`` si ``name`` es un nombre de método privado.

    ≙ ``check_method_name`` (``odoo19c: odoo/orm/utils.py:69-73``). Docstring de
    la fuente, verbatim: *"Raise an ``AccessError`` if ``name`` is a private
    method name"*.

    **Se porta con su aviso de obsolescencia**, que es la mitad que informa: la
    fuente la marcó obsoleta en 19.0 y redirige a ``service.model``. Aquí ese
    sucesor ya existe y hace más —``get_public_method`` rechaza cinco formas,
    no una— así que quien llame a ésta está midiendo un eje de los cinco.
    Retirar el aviso dejaría de decírselo.
    """
    warnings.warn("Since 19.0, use service.model.get_public_method",
                  DeprecationWarning)
    if regex_private.match(name):
        raise AccessError(
            'Private methods (such as %s) cannot be called remotely.' % name)


class OriginIds:
    """Los ids de origen de una colección de ids, recorrible en los dos sentidos.

    ≙ ``OriginIds`` (``odoo19c: odoo/orm/utils.py:129-146``). Docstring de la
    fuente, verbatim: *"A reversible iterable returning the origin ids of a
    collection of ``ids``.  Actual ids are returned as is, and ids without
    origin are not returned"*.

    Las dos mitades del contrato son igual de importantes, y la segunda es la
    que se olvida: un :class:`~orm.identifiers.NewId` **sin** origen no se
    emite. Es lo que hace que recorrer estos ids sea seguro contra la base —
    todo lo que sale tiene fila.

    El truco del cuerpo es el mismo de la fuente y conviene leerlo despacio:
    ``id_ or getattr(id_, 'origin', None)`` se apoya en que ``NewId`` es falsy
    (``identifiers.py``) mientras un id real no lo es. Así una sola expresión
    despacha los dos casos sin preguntar por el tipo.

    No es un generador: guarda la colección, no su recorrido, así que se puede
    recorrer dos veces — que es justo lo que ``__reversed__`` necesita.
    """

    __slots__ = ['ids']

    def __init__(self, ids):
        self.ids = ids

    def __iter__(self):
        for id_ in self.ids:
            if id_ := id_ or getattr(id_, 'origin', None):
                yield id_

    def __reversed__(self):
        for id_ in reversed(self.ids):
            if id_ := id_ or getattr(id_, 'origin', None):
                yield id_


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


def as_record_list(records):
    """Las filas de ``records`` como lista.

    La contraparte de :func:`record_ids` para cuando hace falta el objeto y no
    la clave — un cómputo, un inverso o una escritura de caché se invocan sobre
    la fila, no sobre su id.

    Vivía en ``orm/fields.py`` como ``_as_record_list`` y se movió aquí por la
    segunda cláusula de ``atributos-de-clase-de-modelo.md`` (el SITIO del
    símbolo): su propio docstring ya se declaraba «la contraparte de
    ``orm.utils.record_ids``», y ``orm/models.py`` lo importaba de ``fields``
    con otro nombre. Desde ``fields_relational`` no se podía consumir sin
    invertir el import de ``fields`` — que es un ciclo, no una preferencia.
    """
    if records is None:
        return []
    if isinstance(records, models.Model):
        return [records]
    return list(records)


def model_of(records):
    """La clase de modelo de ``records`` — la vuelta de ``type(recordset)``.

    Tercera pieza de la misma adaptación que :func:`record_ids` y
    :func:`browse`, y por la misma razón: en la fuente un recordset **es** una
    instancia de la clase de registro del modelo, así que ``records.browse(...)``
    y ``records._name`` salen gratis. Aquí un conjunto de filas es una
    instancia de modelo o un ``QuerySet``, y ninguno de los dos responde
    ``browse``; hace falta llegar a la clase para pasársela a :func:`browse`.

    Acepta las tres formas que el árbol produce —instancia, ``QuerySet`` y la
    propia clase— y **rehúsa** cualquier otra con ``TypeError``. Un iterable
    suelto no se admite a propósito: adivinar la clase mirando su primer
    elemento lo consumiría cuando fuera un generador, y devolver ``None`` ante
    lo desconocido convertiría el fallo en un ``AttributeError`` lejano.
    """
    if isinstance(records, models.QuerySet):
        return records.model
    if isinstance(records, models.Model):
        return type(records)
    if isinstance(records, type) and issubclass(records, models.Model):
        return records
    raise TypeError(
        "model_of espera una instancia de modelo, un QuerySet o una clase de "
        "modelo; recibió %r" % (type(records).__name__,)
    )


def browse(model, ids=()):
    """Las filas de ``ids``, en el orden pedido — la adaptación de ``browse``.

    ≙ ``BaseModel.browse`` (``odoo19c: odoo/orm/models.py:5883``). Es la vuelta
    de :func:`record_ids`: aquélla traduce un conjunto de filas a sus ids, ésta
    traduce unos ids al conjunto de filas. La normalización del argumento se
    porta verbatim —el vacío, el entero suelto, el iterable— porque es la
    misma decisión de la fuente y no depende del motor.

    Lo que **sí** diverge es el mecanismo, y son dos puntos:

    - **El orden se reconstruye.** La fuente guarda los ids en una tupla, así
      que conservarlos es gratis. Un ``QuerySet`` no guarda ids: guarda una
      consulta, y el motor devuelve las filas en el orden que le convenga (o en
      el del ``Meta.ordering`` del modelo). El orden pedido se impone con un
      ``CASE`` en el ``ORDER BY``, que es como PostgreSQL expresa «ordena por
      esta lista».
    - **Un id inexistente se descarta, no se difiere.** La fuente no consulta
      nada al construir el recordset: un id que no existe falla más tarde, al
      leerse. Aquí la consulta decide qué filas hay, así que el id sobrante se
      cae del resultado. Por la misma razón un id repetido aparece una vez: una
      fila no se duplica en SQL.

    Las dos divergencias tienen su caso en
    ``tests/unit/orm/test_utils_browse.py``, de modo que el día que este árbol
    construya un conjunto de filas perezoso, esos casos caigan y la decisión se
    vuelva a tomar en vez de heredarse.
    """
    if not ids:
        ids = ()
    elif ids.__class__ is int:
        ids = (ids,)
    else:
        ids = tuple(ids)
    if not ids:
        return model.objects.none()
    given_order = models.Case(
        *[models.When(pk=pk, then=models.Value(position))
          for position, pk in enumerate(ids)],
        output_field=models.IntegerField(),
    )
    return model.objects.filter(pk__in=ids).order_by(given_order)


def model_field_registry(model):
    """El mapa ``nombre -> campo`` de una clase de modelo.

    Es el cuerpo de ``BaseModel._fields`` sacado a funcion para que se pueda
    consultar **sobre la clase**, no solo sobre una instancia. La fuente lo
    tiene asi de nacimiento: su ``Model._fields`` es un atributo de la clase de
    registro, y ``resolve_depends`` lo recorre sin instanciar nada
    (``odoo19c: odoo/orm/fields.py:823``).

    > **Corregido (tarea #342).** Este parrafo decia que aqui ``_fields`` es
    > una ``property`` y que sobre la clase devuelve el objeto ``property``.
    > Era cierto y describia un hueco que esta funcion **tapaba en vez de
    > cerrar**: cada consumidor que tenia la clase y no la fila llamaba aqui a
    > mano. ``_fields`` es ahora un :class:`FieldRegistryDescriptor`, asi que
    > ``Model._fields`` devuelve el mapa igual que allá. La funcion se queda
    > —es el cuerpo que el descriptor invoca, y el que reciben los once sitios
    > que ya la llamaban— pero deja de ser el unico camino desde la clase.

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


class FieldRegistryDescriptor:
    """``_fields`` legible por la clase y por la fila.

    La fuente declara ``_fields`` en la clase de registro, asi que
    ``Model._fields`` y ``record._fields`` devuelven el mismo mapa; su
    ``check_indexes`` lo lee por la clase
    (``odoo19c: odoo/orm/registry.py:813``) y ``resolve_depends`` tambien
    (``odoo/orm/fields.py:823``). Una ``property`` sirve solo la mitad de fila:
    consultada sobre la clase devuelve el objeto descriptor.

    El mecanismo no se trae de fuera. El protocolo de descriptor de CPython ya
    distingue los dos accesos —``__get__`` recibe ``instance=None`` cuando el
    acceso es por la clase, y el ``owner`` que hace falta—, asi que basta
    usarlo en vez de la ``property``, que es el caso particular que solo
    responde a la instancia.
    """

    def __get__(self, instance, owner=None):
        """El mapa del modelo, venga el acceso de la clase o de una fila."""
        return model_field_registry(owner if instance is None else type(instance))


def model_of_field(field, registry_module):
    """La clase de modelo a la que ``field`` pertenece.

    ≙ ``field.model_name`` de la fuente, que es el nombre punteado que su ORM
    le pone al campo al ligarlo (``odoo19c: odoo/orm/fields.py``). Aqui quien
    liga el campo es Django, y lo que deja es ``field.model`` — la clase,
    directamente. Por eso la resolucion tiene **dos vias y la de Django va
    primero**: ``model_name`` solo lo lleva un campo cuyo puerto se lo haya
    declarado, asi que preguntar solo por el dejaria fuera a todo campo ligado
    por Django, que son todos.

    ``registry_module`` se recibe en vez de importarse: ``orm.registry`` importa
    de aqui, y este modulo es la capa de abajo. Es el mismo motivo por el que
    ``model_field_registry`` recibe la clase y no la busca.

    Vive aqui y no en ``orm/fields.py`` —donde nacio como ``_model_of``— porque
    tiene un segundo consumidor que no puede importar aquel archivo:
    ``Environment._recompute_all`` y ``flush_all`` lo necesitan para resolver el
    modelo de un campo sucio, y ``orm/fields.py`` importa ``orm.environments``.
    Copiar las tres lineas seria la segunda fuente de verdad que
    ``calibration-verified-numbers.md`` prohibe.
    """
    model = getattr(field, 'model', None)
    if model is not None:
        return model
    name = getattr(field, 'model_name', '')
    return registry_module.MODELS_BY_NAME.get(name) if name else None


def display_name_of(record):
    """La etiqueta de un registro — ≙ ``record.display_name``.

    Vive aquí y no en ``orm/fields.py``, donde nació, por la misma razón que
    :func:`model_of` una función más arriba: tiene consumidores que **no
    pueden** importar aquel archivo. Son tres, y hasta este pase cada uno
    llevaba su copia:

    - ``orm/fields.py`` — el despachador de ``convert_to_display_name``;
    - ``orm/fields_relational.py`` — la sobrecarga de ``Many2one``, que
      ``orm/fields.py`` importa (``orm/fields.py:86``), así que el import
      inverso sería un ciclo;
    - ``orm/fields_properties.py`` — la etiqueta de un valor de propiedad
      relacional, con el mismo ciclo.

    Tres copias de dos líneas son la segunda fuente de verdad que
    ``calibration-verified-numbers.md`` prohíbe: la tercera se iba a escribir
    en este pase y en su lugar se unificaron las tres.

    Un modelo que aún no adoptó el ``display_name`` universal —los de terceros
    lo son por decisión, el adoptador de ``orm.model_classes`` no los toca—
    cae a ``str(record)``, que es el ``__str__`` de Django.
    """
    label = getattr(record, 'display_name', None)
    return label if label else str(record)
