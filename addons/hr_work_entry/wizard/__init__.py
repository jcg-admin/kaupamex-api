"""Wizards del addon ``hr_work_entry`` — espejo de
``odoo19c: hr_work_entry/wizard/``.

Patrón del árbol (``hr/wizard/__init__.py``): el wizard es una clase sin
tabla (``TransientModel`` con ``Meta: abstract``) que los consumidores
importan directo; este paquete lo re-exporta.
"""
from . import hr_work_entry_regeneration_wizard  # noqa: F401
