"""Decoradores del ORM — fiel a ``odoo/orm/decorators.py`` (Odoo 19).

En Odoo 19 los decoradores ``@api.depends``/``@api.constrains``/``@api.model``…
se **definen** en ``odoo/orm/decorators.py`` y ``odoo/api/__init__.py`` los
re-exporta. Aquí, con el prefijo ``odoo.`` eliminado (``orm`` ≙ ``odoo/orm``),
esta es la **definición**; ``src/api/__init__.py`` (≙ ``odoo/api/__init__.py``)
la re-exporta como el namespace ``api``.

Django no tiene el motor de dependencias del ORM de Odoo: el cómputo se ejecuta
en ``save()`` y la validación en ``clean()``. Estos decoradores **no cambian el
comportamiento** (devuelven la función tal cual) y anotan el metadato ``_odoo_*``
con los campos declarados; permiten conservar el decorador sobre el método
portado para expresar la intención Odoo — el ``save()``/``clean()`` del modelo
es quien realmente los llama.
"""

__all__ = [
    'depends', 'constrains', 'onchange', 'model', 'model_create_multi', 'returns',
    'autovacuum',
]


def depends(*fields):
    def deco(func):
        func._depends = fields
        return func
    return deco


def constrains(*fields):
    def deco(func):
        func._constrains = fields
        return func
    return deco


def onchange(*fields):
    def deco(func):
        func._onchange = fields
        return func
    return deco


def model(func):
    return func


def model_create_multi(func):
    return func


def returns(*args, **kwargs):
    def deco(func):
        return func
    return deco


def autovacuum(method):
    """Marca un método para que lo llame el barrido de ``ir.autovacuum``.

    Fiel a ``odoo/orm/decorators.py:299-310`` (``odoo19c:``), incluida la
    aserción de que el nombre sea privado: allá el mensaje es *"autovacuum
    methods must be private"*. Sirve para tareas de recolección que no ameritan
    un cron propio.

    El valor de retorno puede ser la tupla ``(hechos, restantes)``; si
    ``restantes`` es verdadero, el colector vuelve a encolar el método.
    """
    assert method.__name__.startswith('_'), (
        '%s: los métodos de autovacuum deben ser privados' % method.__name__
    )
    method._autovacuum = True
    return method
