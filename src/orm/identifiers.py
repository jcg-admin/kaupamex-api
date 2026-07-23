"""Identificadores del ORM — fiel a ``odoo/orm/identifiers.py`` (Odoo 19).

``NewId`` es un pseudo-id para registros aún no persistidos (creaciones en
memoria, onchange). Es **puro Python, sin dependencia del motor**, así que se
porta fiel (no es un stub): un addon que replique el patrón onchange de Odoo lo
usa idéntico. En Django el equivalente de "registro sin PK todavía" es una
instancia con ``pk is None``; ``NewId`` añade el matiz Odoo de un id-falso con
``origin`` (id real del que deriva) y ``ref`` (referencia arbitraria), que Django
no modela por sí mismo.
"""
import functools
import typing


@functools.total_ordering
class NewId:
    """Pseudo-id para registros nuevos, encapsula un ``origin`` (id real
    opcional) y una ``ref`` (valor arbitrario opcional). Fiel a Odoo 19."""
    __slots__ = ('origin', 'ref', '__hash')  # noqa: RUF023

    def __init__(self, origin=None, ref=None):
        self.origin = origin
        self.ref = ref
        self.__hash = hash(origin or ref or id(self))

    def __bool__(self):
        return False

    def __eq__(self, other):
        return isinstance(other, NewId) and (
            (self.origin and other.origin and self.origin == other.origin)
            or (self.ref and other.ref and self.ref == other.ref)
        )

    def __hash__(self):
        return self.__hash

    def __lt__(self, other):
        if isinstance(other, NewId):
            other = other.origin
            if other is None:
                return other > self.origin if self.origin else False
        if isinstance(other, int):
            return bool(self.origin) and self.origin < other
        return NotImplemented

    def __repr__(self):
        return (
            "<NewId origin=%r>" % self.origin if self.origin else
            "<NewId ref=%r>" % self.ref if self.ref else
            "<NewId 0x%x>" % id(self)
        )

    def __str__(self):
        if self.origin or self.ref:
            id_part = repr(self.origin or self.ref)
        else:
            id_part = hex(id(self))
        return "NewId_%s" % id_part


# Por defecto el ORM lo inicializa como int, pero cualquier tipo es válido;
# partes del ORM asumen entero (fields relacionales, referencias, jerarquías).
IdType: typing.TypeAlias = int | NewId | str
