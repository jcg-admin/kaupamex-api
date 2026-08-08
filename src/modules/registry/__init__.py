"""Shim de compatibilidad — fiel a ``odoo/modules/registry/__init__.py``.

En la referencia este archivo son **3 líneas** que re-exportan de
``odoo/orm/registry.py`` ("Exposed here so that exist code is unaffected"), para
que ``from odoo.modules.registry import Registry`` siga resolviendo tras mover la
definición al ORM. Aquí se conserva la misma indirección sobre ``orm.registry``.

Ojo con lo que se re-exporta: ``orm/registry.py`` de este árbol **no define una
clase ``Registry``** — documenta que ``django.apps.apps`` YA es el registro de
modelos y que recrearlo duplicaría ``django.apps``. Por eso lo que viaja por este
shim es ``apps`` y ``connections``, no un ``Registry`` inventado: un import de
``Registry`` debe fallar en vez de devolver un objeto que no gobierna nada.
"""
from orm.registry import apps, connections   # noqa: F401

__all__ = ['apps', 'connections']
