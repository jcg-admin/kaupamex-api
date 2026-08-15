"""``tools.func`` — espejo de ``odoo/tools/func.py`` (sólo símbolos con consumidor).

Misma regla que ``tools/misc.py``: un símbolo llega aquí cuando un módulo
portado lo importa (``from tools.func import X``, espejo de ``from odoo.tools
import X``), y **antes de portarlo se decide** si el stdlib ya lo resuelve. La
decisión queda en el docstring del símbolo — no se porta por completitud.

Censo de la fuente (``odoo19c: odoo/tools/func.py``): nueve símbolos —
``reset_cached_properties``, ``lazy_property``, ``conditional``,
``filter_kwargs``, ``synchronized``, ``frame_codeinfo``, ``classproperty``,
``lazy_classproperty`` y ``lazy``. Portado **uno**: ``classproperty``, que es
el que ``orm/domains.py`` consume. Los otros ocho no tienen consumidor en este
árbol; su porte se decide cuando lo tengan.

Adaptado de Odoo Community ``odoo/tools/func.py`` (LGPL-3) — atribución y
aviso de licencia preservados (DEC-KX-03).
"""
import typing

__all__ = ['classproperty']

T = typing.TypeVar('T')


class classproperty(typing.Generic[T]):
    """Una ``property`` que se resuelve sobre la clase — ≙ ``func.py:115-125``.

    ``orm/domains.py`` la consume en tres sitios: ``Domain.TRUE``,
    ``Domain.FALSE`` y ``DomainNary.INVERSE``. Los tres devuelven objetos que
    sólo existen **después** del cuerpo de la clase que los declara —los dos
    singletons ``DomainBool`` y la clase hermana ``DomainAnd``/``DomainOr``—,
    así que un atributo de clase normal no puede declararlos donde la fuente
    los declara.

    Python no la trae. Encadenar ``@classmethod`` con ``@property`` funcionaba
    en 3.9-3.10 y quedó **retirado en 3.11**; este proyecto corre 3.12+
    (``pyproject.toml``), así que ese camino no existe. De ahí que se porte en
    vez de aliasarse.
    """

    def __init__(self, fget):
        self.fget = classmethod(fget)

    def __get__(self, cls, owner=None, /):
        return self.fget.__get__(None, owner)()

    @property
    def __doc__(self):
        return self.fget.__doc__
