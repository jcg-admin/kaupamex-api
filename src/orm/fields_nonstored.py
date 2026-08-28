"""Campo no persistido — ≙ el ``store=False`` de la referencia.

En Odoo un campo puede declararse **sin columna**: ``fields.Char(store=False,
default=_get_algo)`` produce un atributo que se calcula al leerlo y nunca se
escribe a la base (``odoo19c: account/models/res_currency.py:17`` es el caso
canónico). Django no lo tiene: todo ``models.Field`` es una columna.

Este módulo lo construye. No es una comodidad: sin él, portar
``fiscal_country_codes`` obligaba a inventar una forma distinta —una
``property`` colgada desde otro addon— y a repartir en el cableado lo que la
referencia declara **en la clase**. Es la diferencia entre adaptar la conducta
y copiar una restricción ajena.

Qué NO es
==========

- **No es un campo de Django.** No aparece en ``_meta.get_fields()``, no genera
  migración, no se puede filtrar con ``.filter(campo=…)``. Es exactamente lo
  que la referencia promete con ``store=False``: un valor que existe para
  leerse, no para consultarse.
- **No es una ``property``.** Admite asignación —``obj.campo = 'X'`` se guarda
  en la instancia y gana sobre el ``default``—, igual que en la referencia,
  donde un campo no almacenado sigue siendo escribible en memoria.

Cómo se declara
================

Con la misma firma que la fuente, en el cuerpo de la clase o colgado después::

    fiscal_country_codes = fields.Char(store=False,
                                       default=get_fiscal_country_codes)

El ``default`` puede ser un valor o un invocable. Si es invocable se llama con
la instancia cuando acepta un argumento, y sin argumentos cuando no — así
sirven tanto un cómputo que mira sólo la sesión (``env.companies`` en la
referencia) como uno que mira el registro (``record.company_id or …``).

Este archivo NO existe en la referencia, y ``src/orm`` es una raíz espejada
==========================================================================

Medido contra ``odoo19c: odoo/orm/`` — ``find`` por nombre y ``grep`` por
símbolo, los dos a **0**. La referencia no lo necesita: su ``fields.Char(store=False, ...)`` ya declara un campo sin columna. Este mecanismo existe porque en Django todo ``models.Field`` **es** una columna.

Eso lo hace legítimo como **mecanismo construido**
(``porte-completo-no-parcial.md``: *si el stack no trae el mecanismo, se
construye*) y a la vez lo deja **fuera de sitio**: ``src/orm`` es la raíz
espejada de ``odoo/orm``, y ``atributos-de-clase-de-modelo.md`` §2 manda listar
la raíz de la referencia antes de crear un archivo ahí.

``check_porte_completo`` **no puede verlo**: compara símbolos dentro de un par
de archivos, y un archivo que la referencia no tiene no entra en ninguna
comparación. Cinco archivos de ``src/orm`` están en esta situación —
``checks``, ``fields_nonstored``, ``inherits``, ``method_chain``, ``routers``—
y hasta este pase sólo ``checks`` lo declaraba.

El veredicto por archivo —quedarse aquí con la divergencia declarada, o mudarse
a una raíz propia como ``src/core``— es la tarea **#121**.
"""
import inspect

__all__ = ['NonStored']


class NonStored:
    """Descriptor de un campo declarado ``store=False``.

    Sigue el protocolo de ``contribute_to_class`` de Django para que funcione
    en los dos caminos por los que un atributo llega a un modelo: el cuerpo de
    la clase (``ModelBase`` lo invoca) y ``Model.add_to_class`` (el que usan
    las extensiones ``_inherit`` de este puerto). Sin él, el segundo camino
    dejaría el descriptor sin saber su propio nombre.
    """

    def __init__(self, *_args, default=None, help_text='', **_ignored):
        self.default = default
        self.help_text = help_text
        self.name = None

    # -- protocolo de nombre ------------------------------------------------

    def __set_name__(self, owner, name):
        """Camino del cuerpo de clase en una clase que NO es modelo Django."""
        self.name = name

    def contribute_to_class(self, cls, name, **_kwargs):
        """Camino de ``ModelBase`` y de ``add_to_class``.

        Django llama a este método en vez de ``setattr`` cuando el objeto lo
        declara. Aquí **no** se registra nada en ``_meta``: ese es justamente
        el punto — el campo no tiene columna.
        """
        self.name = name
        setattr(cls, name, self)

    # -- protocolo de descriptor -------------------------------------------

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        if self.name in instance.__dict__:
            return instance.__dict__[self.name]
        return self.resolve_default(instance)

    def __set__(self, instance, value):
        instance.__dict__[self.name] = value

    def __delete__(self, instance):
        instance.__dict__.pop(self.name, None)

    # -- resolución del default --------------------------------------------

    def resolve_default(self, instance):
        """Llama al ``default`` con la instancia sólo si la acepta.

        La referencia pasa siempre ``self`` porque allá el ``default`` es un
        método del modelo. Aquí el mismo cómputo puede ser una función suelta
        que no necesita el registro —el caso de los que sólo miran la sesión—,
        y obligarla a aceptar un parámetro que ignora sería ruido en cada uno.
        Se inspecciona la firma una vez por lectura, que es barato frente a la
        consulta que el propio cómputo hace.
        """
        if not callable(self.default):
            return self.default
        try:
            firma = inspect.signature(self.default)
        except (TypeError, ValueError):
            # Invocable sin firma introspectable (builtin, C-extension): se
            # llama sin argumentos, que es la forma más común de ese caso.
            return self.default()
        if len(firma.parameters) >= 1:
            return self.default(instance)
        return self.default()
