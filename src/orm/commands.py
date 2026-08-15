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
    """Operaciones one2many/many2many (Odoo ``Command``)."""

    @staticmethod
    def create(manager, **values):
        """``Command.create`` (0): crea y enlaza un hijo."""
        return manager.create(**values)

    @staticmethod
    def link(manager, obj):
        """``Command.link`` (4): enlaza un registro existente (m2m)."""
        manager.add(obj)

    @staticmethod
    def update(obj, **values):
        """``Command.update`` (1): escribe campos sobre un hijo existente.

        Era el único de los siete que faltaba. Lo pidió el porte de
        ``stock_move._set_quantity_done_prepare_vals``
        (``odoo19c: addons/stock/models/stock_move.py:2490``), que reparte la
        cantidad entre las líneas existentes actualizando unas y borrando otras.

        Como el resto de esta clase, es **ejecutivo**: escribe al llamarlo, en
        vez de devolver una tupla que el ORM aplique después. Esa divergencia
        es de la clase entera y está registrada en :ref:`h-api-589` (tarea
        **#345**), no de este método.
        """
        for campo, valor in values.items():
            setattr(obj, campo, valor)
        obj.save(update_fields=[*values, 'updated_at'] if hasattr(obj, 'updated_at')
                 else list(values))
        return obj

    @staticmethod
    def unlink(manager, obj):
        """``Command.unlink`` (3): desenlaza sin borrar (m2m)."""
        manager.remove(obj)

    @staticmethod
    def delete(obj):
        """``Command.delete`` (2): borra el hijo."""
        obj.delete()

    @staticmethod
    def set(manager, objs):
        """``Command.set`` (6): reemplaza el conjunto (m2m)."""
        manager.set(objs)

    @staticmethod
    def clear(manager):
        """``Command.clear`` (5): desenlaza todos (m2m)."""
        manager.clear()
