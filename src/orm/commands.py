"""``Command`` — helper x2many, fiel a ``odoo/orm/commands.py`` (Odoo 19).

En Odoo 19 ``Command`` vive en ``odoo/orm/commands.py`` y se re-exporta como
``odoo.fields.Command`` / ``odoo.Command``. Aquí, con el prefijo ``odoo.``
eliminado (convención del proyecto: ``orm`` ≙ ``odoo/orm``), un addon escribe
``from orm.commands import Command``.

Reproduce la intención de cada tupla-comando de Odoo (0=create, 1=update,
2=delete, 3=unlink, 4=link, 5=clear, 6=set) como método sobre el *related
manager* de Django.
"""


class Command:
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
    """

    CREATE = 0
    UPDATE = 1
    DELETE = 2
    UNLINK = 3
    LINK = 4
    CLEAR = 5
    SET = 6

    @staticmethod
    def create(*args, **values):
        """``(CREATE, 0, values)`` — o, ejecutivo, crea y enlaza un hijo."""
        if len(args) == 1 and isinstance(args[0], dict) and not values:
            return (Command.CREATE, 0, args[0])
        (manager,) = args
        return manager.create(**values)

    @staticmethod
    def update(target, values=None, **kwargs):
        """``(UPDATE, id, values)`` — o, ejecutivo, escribe sobre un hijo.

        La forma ejecutiva la pidió el porte de
        ``stock_move._set_quantity_done_prepare_vals``
        (``odoo19c: addons/stock/models/stock_move.py:2490``).
        """
        if _is_id(target):
            return (Command.UPDATE, target, values if values is not None else kwargs)
        if values is not None:
            kwargs = {**values, **kwargs}
        for campo, valor in kwargs.items():
            setattr(target, campo, valor)
        target.save(
            update_fields=(
                [*kwargs, 'updated_at']
                if hasattr(target, 'updated_at')
                else list(kwargs)
            )
        )
        return target

    @staticmethod
    def delete(target):
        """``(DELETE, id, 0)`` — o, ejecutivo, borra el hijo."""
        if _is_id(target):
            return (Command.DELETE, target, 0)
        target.delete()

    @staticmethod
    def unlink(*args):
        """``(UNLINK, id, 0)`` — o, ejecutivo, desenlaza sin borrar (m2m)."""
        if len(args) == 1:
            return (Command.UNLINK, args[0], 0)
        manager, obj = args
        manager.remove(obj)

    @staticmethod
    def link(*args):
        """``(LINK, id, 0)`` — o, ejecutivo, enlaza un registro (m2m)."""
        if len(args) == 1:
            return (Command.LINK, args[0], 0)
        manager, obj = args
        manager.add(obj)

    @staticmethod
    def clear(*args):
        """``(CLEAR, 0, 0)`` — o, ejecutivo, desenlaza todos (m2m)."""
        if not args:
            return (Command.CLEAR, 0, 0)
        (manager,) = args
        manager.clear()

    @staticmethod
    def set(*args):
        """``(SET, 0, ids)`` — o, ejecutivo, reemplaza el conjunto (m2m)."""
        if len(args) == 1:
            return (Command.SET, 0, list(args[0]))
        manager, objs = args
        manager.set(objs)


def _is_id(value):
    """Un identificador de fila de la fuente: ``int`` que no sea ``bool``."""
    return type(value) is int


def is_command_list(value):
    """``True`` si ``value`` es una lista de triples de comando de la fuente."""
    return (isinstance(value, (list, tuple)) and bool(value)
            and all(isinstance(item, (list, tuple)) and len(item) == 3
                    and type(item[0]) is int for item in value))


def _row_id(value):
    """El id de un elemento de un ``SET``: un entero o una fila/recordset."""
    if _is_id(value):
        return value
    ids = getattr(value, '_ids', None)
    if ids is not None:
        return ids[0] if ids else None
    return getattr(value, 'pk', value)


def apply_many2many_commands(record, field, value):
    """Aplica el valor x2many de la fuente sobre el manager de un ``Many2many``.

    ≙ ``Many2many.write_real`` (``odoo19c: odoo/orm/fields_relational.py``):
    los siete comandos, más las dos abreviaturas que ``convert_to_cache``
    admite —una lista de ids o de registros es ``SET`` y ``False``/``None``
    es ``CLEAR``—. El manager de Django emite ``m2m_changed`` en cada
    operación, que es donde vive el control de acceso de la relación.
    """
    manager = getattr(record, field.name)
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
    for code, target, payload in value:
        if code == Command.CREATE:
            created = (comodel.create(payload) if hasattr(comodel, 'create')
                       else comodel.objects.create(**payload))
            manager.add(_row_id(created))
        elif code == Command.UPDATE:
            row = comodel._base_manager.get(pk=target)
            row.write(payload)
        elif code == Command.DELETE:
            manager.remove(target)
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
