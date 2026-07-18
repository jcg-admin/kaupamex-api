"""Decoradores de modelo — fiel a ``odoo/api.py`` (Odoo 18/19).

Módulo top-level (prefijo ``odoo.`` eliminado por la convención del proyecto,
igual que ``orm``/``tools``): un addon escribe ``import api`` y usa
``@api.depends(...)``, leyendo como su fuente Odoo (``from odoo import api``).

Odoo usa ``@api.depends``/``@api.constrains``/``@api.model``/``@api.onchange``
para declarar cómputos y validaciones que su ORM invoca. Django no tiene ese
motor: el cómputo se ejecuta en ``save()`` y la validación en ``clean()``. Estos
decoradores **no cambian el comportamiento** (devuelven la función tal cual) y
anotan el metadato ``_odoo_*`` con los campos declarados; permiten conservar el
decorador sobre el método portado para expresar la intención Odoo. El
``save()``/``clean()`` del modelo es quien realmente los llama.
"""


def depends(*fields):
    def deco(func):
        func._odoo_depends = fields
        return func
    return deco


def constrains(*fields):
    def deco(func):
        func._odoo_constrains = fields
        return func
    return deco


def onchange(*fields):
    def deco(func):
        func._odoo_onchange = fields
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
