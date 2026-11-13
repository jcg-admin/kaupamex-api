"""``Command`` — helper x2many, fiel a ``odoo/orm/commands.py`` (Odoo 19).

En Odoo 19 ``Command`` vive en ``odoo/orm/commands.py`` y se re-exporta como
``odoo.fields.Command`` / ``odoo.Command``. Aquí, con el prefijo ``odoo.``
eliminado (convención del proyecto: ``orm`` ≙ ``odoo/orm``), un addon escribe
``from orm.commands import Command``.

Reproduce la intención de cada tupla-comando de Odoo (0=create, 1=update,
2=delete, 3=unlink, 4=link, 5=clear, 6=set) como método sobre el *related
manager* de Django.
"""

import enum

from django.db import models as _django_models
from django.db.models.fields import related_descriptors as _related_descriptors

from exceptions import MissingError
from orm.environments import Environment, env, get_current_uid, get_transaction


class Command(enum.IntEnum):
    """Operaciones one2many/many2many — ≙ ``odoo19c: odoo/orm/commands.py``.

    **Las dos formas conviven, y la aridad las distingue.** La fuente es un
    ``IntEnum`` cuyos métodos devuelven el triple diferido
    ``(código, id, valores)`` que ``create``/``write`` interpretan:
    ``Command.link(7)`` es ``(4, 7, 0)``. Este árbol nació con una forma
    **ejecutiva** —``Command.link(manager, obj)`` escribe al llamarla— y la
    usan ``stock`` (``clear(manager)``, ``delete(obj)``, ``update(obj,
    **vals)``). Cada método mira lo que recibe: un id, una lista de ids, un
    ``dict`` o nada es la forma de la fuente; un manager o una fila es la
    ejecutiva. :func:`apply_many2many_commands` interpreta los triples.

    Como en la fuente, la clase es un ``IntEnum`` (``:11``): el primer elemento
    del triple es el **miembro** (``Command.LINK``), que compara igual a su
    entero, y ``Command(4)`` resuelve el código literal que llega por RPC.
    """

    CREATE = 0
    UPDATE = 1
    DELETE = 2
    UNLINK = 3
    LINK = 4
    CLEAR = 5
    SET = 6

    @classmethod
    def create(cls, *args, **values):
        """``(CREATE, 0, values)`` — o, ejecutivo, crea y enlaza un hijo."""
        if len(args) == 1 and isinstance(args[0], dict) and not values:
            return (cls.CREATE, 0, args[0])
        (manager,) = args
        return manager.create(**values)

    @classmethod
    def update(cls, target, values=None, **kwargs):
        """``(UPDATE, id, values)`` — o, ejecutivo, escribe sobre un hijo.

        La forma ejecutiva la pidió el porte de
        ``stock_move._set_quantity_done_prepare_vals``
        (``odoo19c: addons/stock/models/stock_move.py:2490``).
        """
        if _is_id(target):
            return (cls.UPDATE, target,
                    values if values is not None else kwargs)
        if values is not None:
            kwargs = {**values, **kwargs}
        for campo, valor in kwargs.items():
            setattr(target, campo, valor)
        target.save(
            update_fields=(
                [*kwargs, 'write_date']
                if hasattr(target, 'write_date')
                else list(kwargs)
            )
        )
        return target

    @classmethod
    def delete(cls, target):
        """``(DELETE, id, 0)`` — o, ejecutivo, borra el hijo."""
        if _is_id(target):
            return (cls.DELETE, target, 0)
        target.delete()

    @classmethod
    def unlink(cls, *args):
        """``(UNLINK, id, 0)`` — o, ejecutivo, desenlaza sin borrar (m2m)."""
        if len(args) == 1:
            return (cls.UNLINK, args[0], 0)
        manager, obj = args
        manager.remove(obj)

    @classmethod
    def link(cls, *args):
        """``(LINK, id, 0)`` — o, ejecutivo, enlaza un registro (m2m)."""
        if len(args) == 1:
            return (cls.LINK, args[0], 0)
        manager, obj = args
        manager.add(obj)

    @classmethod
    def clear(cls, *args):
        """``(CLEAR, 0, 0)`` — o, ejecutivo, desenlaza todos (m2m)."""
        if not args:
            return (cls.CLEAR, 0, 0)
        (manager,) = args
        manager.clear()

    @classmethod
    def set(cls, *args):
        """``(SET, 0, ids)`` — o, ejecutivo, reemplaza el conjunto (m2m)."""
        if len(args) == 1:
            # ``:126`` devuelve ``ids`` tal cual, sin copiarlo.
            return (cls.SET, 0, args[0])
        manager, objs = args
        manager.set(objs)


def _is_id(value):
    """Un identificador de fila de la fuente: ``int`` que no sea ``bool``."""
    return type(value) is int


def is_command_list(value):
    """``True`` si ``value`` es una lista de comandos x2many de la fuente.

    El código es un ``int`` —el literal de RPC o el miembro de
    :class:`Command`, que es un ``IntEnum``—, nunca un ``bool``. La fuente
    lee cada comando por índice (``command[0]``, ``command[1]``,
    ``command[2]``; ``odoo19c: odoo/orm/fields_relational.py:1464-1481``), así
    que también son comandos las formas cortas que escriben sus archivos de
    datos: ``(4, id)``, ``(3, id)`` y ``(5,)``. Las recorre
    :func:`command_triples`.
    """
    return (isinstance(value, (list, tuple)) and bool(value)
            and all(isinstance(item, (list, tuple)) and 1 <= len(item) <= 3
                    and isinstance(item[0], int)
                    and not isinstance(item[0], bool) for item in value))


def command_triples(commands):
    """Cada comando como ``(código, objetivo, carga)``, con lo que falta en
    ``0`` — la lectura por índice de la fuente sobre una forma corta."""
    for command in commands:
        code, target, payload = (tuple(command) + (0, 0))[:3]
        yield code, target, payload


def _row_id(value):
    """El id de un elemento de un ``SET``: un entero o una fila/recordset."""
    if _is_id(value):
        return value
    ids = getattr(value, '_ids', None)
    if ids is not None:
        return ids[0] if ids else None
    if isinstance(value, _django_models.QuerySet):
        # el alta de un comodelo sin ``BaseModel`` devuelve el ``QuerySet``
        # de ``_create_result``, no una fila
        return value.values_list('pk', flat=True).first()
    return getattr(value, 'pk', value)


#: El ``__get__`` de Django de los x2many, tomado antes de que
#: ``orm.models`` lo sustituya para devolver un recordset.
_DJANGO_X2MANY_GET = _related_descriptors.ReverseManyToOneDescriptor.__get__


def related_manager(record, name):
    """El gestor de Django de un x2many, también cuando leer el campo
    devuelve un recordset (``orm.models._x2many_descriptor_get``).

    Lo usan los consumidores internos que escriben la relación (``set``,
    ``add``, ``clear``): este intérprete, ``create`` y ``_check_company``.
    """
    return _DJANGO_X2MANY_GET(getattr(type(record), name), record)


def _record_env(record):
    """El entorno del registro — ``model.env`` de la referencia.

    Un recordset lleva el suyo; una fila de Django sin ``BaseModel`` actúa en
    el ambiental, que es el único que tiene.
    """
    environment = getattr(record, 'env', None)
    return environment if isinstance(environment, Environment) else env()


def comodel_records(scope, comodel):
    """El comodelo como lo usa la fuente: ``model.env[comodel_name]``, el
    recordset vacío del entorno.

    ``scope`` es el entorno, o el registro del que se toma (``_record_env``:
    una fila de Django sin ``BaseModel`` actúa en el ambiental). Un comodelo
    de Django sin ``BaseModel`` no tiene recordset y sigue como clase, con su
    manager.
    """
    if not hasattr(comodel, '_from_ids'):
        return comodel
    environment = (scope if isinstance(scope, Environment)
                   else _record_env(scope))
    return environment[comodel._name]


def _check_sudo_commands(environment, comodel):
    """El entorno en que corren los comandos sobre ``comodel`` — ≙
    ``_RelationalMulti._check_sudo_commands`` (``odoo19c:
    odoo/orm/fields_relational.py:772-777``).

    Un comodelo con ``_allow_sudo_commands = False`` no admite comandos bajo
    ``sudo()`` ni con otro usuario: corren sin elevación y con el usuario por
    defecto de la transacción (``transaction.default_env.uid``).

    Divergencia declarada: este árbol fija el usuario de la petición en el
    canal ambiental (``set_current_uid``) y no construye un ``default_env``;
    sin él, el usuario por defecto es el del canal ambiental.
    """
    if getattr(comodel, '_allow_sudo_commands', True):
        return environment
    default_env = get_transaction().default_env
    default_uid = (default_env.uid if default_env is not None
                   else get_current_uid())
    return environment(user=default_uid, su=False)


def apply_many2many_commands(record, field, value):
    """Aplica el valor x2many de la fuente sobre el manager de un
    ``Many2many``.

    ≙ ``Many2many.write_real`` (``odoo19c: odoo/orm/fields_relational.py``):
    los siete comandos, más las dos abreviaturas que ``convert_to_cache``
    admite —una lista de ids o de registros es ``SET`` y ``False``/``None``
    es ``CLEAR``—. El manager de Django emite ``m2m_changed`` en cada
    operación, que es donde vive el control de acceso de la relación.
    """
    manager = related_manager(record, field.name)
    if value is None or value is False:
        manager.clear()
        return
    if not is_command_list(value):
        if isinstance(value, (list, tuple)):
            manager.set([_row_id(item) for item in value if _row_id(item)])
        else:
            manager.set(value)
        return
    comodel = field.related_model
    with _check_sudo_commands(_record_env(record), comodel) as environment:
        _apply_many2many_triples(
            manager, comodel_records(environment, comodel), value)


def _apply_many2many_triples(manager, comodel, value):
    """Los triples de ``Many2many.write_real`` (``:1460-1495``), dentro del
    entorno que :func:`_check_sudo_commands` decide."""
    for code, target, payload in command_triples(value):
        if code == Command.CREATE:
            created = (comodel.create(payload) if hasattr(comodel, 'create')
                       else comodel.objects.create(**payload))
            manager.add(_row_id(created))
        elif code == Command.UPDATE:
            for line in _line_rows(comodel, [target]):
                _write_line(line, payload)
        elif code == Command.DELETE:
            manager.remove(target)
            if hasattr(comodel, 'browse'):
                # ``comodel.browse(to_delete).unlink()`` (``:1491``).
                comodel.browse([target]).unlink()
            else:
                comodel._base_manager.filter(pk=target).delete()
        elif code == Command.UNLINK:
            manager.remove(target)
        elif code == Command.LINK:
            manager.add(target)
        elif code == Command.CLEAR:
            manager.clear()
        elif code == Command.SET:
            manager.set([_row_id(item) for item in payload if _row_id(item)])
        else:
            raise ValueError(f'Comando x2many desconocido: {code!r}')


def _line_rows(comodel, ids):
    """Las filas de ``ids`` en el orden dado; un recordset si el comodelo es
    ``BaseModel``."""
    ids = [i for i in ids if i]
    if hasattr(comodel, 'browse'):
        return list(comodel.browse(ids))
    rows = comodel._base_manager.in_bulk(ids)
    return [rows[i] for i in ids if i in rows]


def _write_line(line, values):
    if hasattr(line, 'write'):
        line.write(values)
    else:
        for name, value in values.items():
            setattr(line, name, value)
        line.save(update_fields=list(values))


def apply_one2many_commands(record, rel, value, create=False):
    """Aplica los comandos de un One2many en el entorno que
    :func:`_check_sudo_commands` decide para el comodelo — ≙ la cabecera de
    ``One2many.write_real`` (``odoo19c: odoo/orm/fields_relational.py:
    975-977``)."""
    with _check_sudo_commands(_record_env(record),
                              rel.related_model) as environment:
        _apply_one2many_triples(record, rel, value, create, environment)


def _apply_one2many_triples(record, rel, value, create, environment):
    """Aplica los comandos de un One2many sobre su inverso — ≙
    ``One2many.write_real`` (``odoo19c: odoo/orm/fields_relational.py:
    969-1045``), rama almacenada, para un solo registro.

    ``rel`` es la relación inversa de Django (el ``ManyToOneRel`` del
    ``Many2one`` del comodelo). Se conservan las tres colas de la fuente
    —crear, borrar, enlazar— y su ``flush``: enlazar resta lo que el
    registro ya tenía antes de escribir, así que un ``LINK`` a una línea ya
    enlazada no la reescribe, y uno a una línea ausente lanza
    ``MissingError``. En ``create`` un ``SET``/``CLEAR`` no borra nada: se
    lee como ``LINK``, como en la fuente (``allow_full_delete``).

    pendiente: el ``domain`` del One2many (``get_comodel_domain``) en
    ``SET``/``CLEAR`` y el ``context`` del campo; ningún inverso de Django
    los declara aquí.
    """
    comodel = rel.related_model
    records = comodel_records(environment, comodel)
    inverse = rel.field.name
    cascade = rel.field.remote_field.on_delete is _django_models.CASCADE
    to_create, to_delete, to_link = [], [], []
    allow_full_delete = not create

    def current_ids():
        return list(comodel._base_manager.filter(**{inverse: record.pk})
                    .values_list('pk', flat=True))

    def unlink(ids):
        if cascade:
            to_delete.extend(ids)
        else:
            for line in _line_rows(records, ids):
                _write_line(line, {inverse: None})

    def flush():
        before = set(current_ids()) if to_link else set()
        if to_delete:
            rows = _line_rows(records, list(dict.fromkeys(to_delete)))
            if hasattr(records, 'browse'):
                records.browse([row.id for row in rows]).unlink()
            else:
                comodel._base_manager.filter(
                    pk__in=[row.pk for row in rows]).delete()
            to_delete.clear()
        if to_create:
            if hasattr(records, 'create'):
                records.create(list(to_create))
            else:
                for vals in to_create:
                    comodel.objects.create(**vals)
            to_create.clear()
        if to_link:
            ids = [i for i in dict.fromkeys(to_link) if i not in before]
            existing = set(comodel._base_manager.filter(pk__in=ids)
                           .values_list('pk', flat=True))
            missing = [i for i in ids if i not in existing]
            if missing:
                # linking missing lines should fail
                raise MissingError(
                    f'Record does not exist or has been deleted: '
                    f'{comodel._meta.label}({missing})')
            for line in _line_rows(records, ids):
                _write_line(line, {inverse: record.pk})
            to_link.clear()

    for code, target, payload in command_triples(value):
        if code == Command.CREATE:
            to_create.append(dict(payload, **{inverse: record.pk}))
            allow_full_delete = False
        elif code == Command.UPDATE:
            for line in _line_rows(records, [target]):
                _write_line(line, payload)
        elif code == Command.DELETE:
            to_delete.append(target)
        elif code == Command.UNLINK:
            unlink([target])
        elif code == Command.LINK:
            to_link.append(target)
            allow_full_delete = False
        elif code in (Command.CLEAR, Command.SET):
            line_ids = ([_row_id(item) for item in payload]
                        if code == Command.SET else [])
            if not allow_full_delete:
                # do not try to delete anything in creation mode if nothing
                # has been created before
                to_link.extend(i for i in line_ids if i)
                continue
            flush()
            keep = set(line_ids)
            unlink([i for i in current_ids() if i not in keep])
            flush()
            for line in _line_rows(records, line_ids):
                _write_line(line, {inverse: record.pk})
        else:
            raise ValueError(f'Comando x2many desconocido: {code!r}')
    flush()


# === Los tres valores diferidos del cargador de datos ======================
#
# ≙ lo que ``Command.set`` / ``Command.link`` / ``Command.create`` devuelven en
# la referencia cuando el converter de importación los produce
# (``odoo19c: addons/base/models/ir_fields.py:657-740``).
#
# Los portadores que el cargador de datos produce. Nacieron cuando ``Command``
# sólo era ejecutivo (:ref:`h-api-589`); hoy ``Command`` también devuelve el
# triple de la fuente, pero el cargador sigue entregando estos tres y los
# aplica ``orm.models.RecordLoaderMixin`` cuando el registro ya existe, que es
# el momento en que Django admite tocar una relación de muchos.


class ManyToManySet(list):
    """El conjunto queda **exactamente** en estos ids — ≙ ``Command.set``."""


class ManyToManyLink(list):
    """Estos ids se **añaden** a los que ya hubiera — ≙ ``Command.link``."""


class One2manyChild:
    """Un hijo a crear o a actualizar — ≙ ``Command.create`` / ``update``.

    Con ``id``, el hijo ya existe: se enlaza y se le escriben los valores
    encima. Sin él, se crea. Es la misma partición que la fuente expresa con
    dos comandos seguidos (``link`` + ``update``) frente a uno (``create``).
    """

    __slots__ = ('id', 'values')

    def __init__(self, id, values):
        self.id = id
        self.values = values

    def __eq__(self, other):
        return isinstance(other, One2manyChild) and (self.id, self.values) == (
            other.id,
            other.values,
        )

    def __repr__(self):
        return 'One2manyChild(%r, %r)' % (self.id, self.values)
