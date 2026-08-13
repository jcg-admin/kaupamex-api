"""Modelos del addon ``uom`` — paquete espejo de ``uom/models/`` (referencia).

Un solo modelo, igual que la referencia: ``uom_uom.py`` → ``Uom``
(``uom.uom``). El addon no extiende ningún modelo ajeno (0 extensiones), así
que su superficie es exactamente esta.
"""
from .uom_uom import Uom

__all__ = ['Uom']
