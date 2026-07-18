"""Excepciones de la plataforma — fiel a ``odoo/exceptions.py`` (Odoo 18/19).

Módulo top-level (hermano de ``addons``, ``orm``, ``tools``), con el prefijo
``odoo.`` eliminado por la convención del proyecto (``pythonpath=src``): igual
que ``orm`` ≙ ``odoo/orm`` y ``tools`` ≙ ``odoo/tools``, aquí ``exceptions`` ≙
``odoo/exceptions``. Un addon portado escribe ``from exceptions import
UserError, ValidationError``, leyendo como su fuente Odoo (``from odoo.exceptions
import UserError``).

Respaldo en Django:

- ``ValidationError`` ← ``django.core.exceptions.ValidationError`` (valida
  campo/constraint).
- ``UserError`` — error de negocio mostrable al usuario; interrumpe una
  operación por regla de negocio (p. ej. postear un asiento no balanceado).
- ``AccessError`` ← ``django.core.exceptions.PermissionDenied``.
- ``RedirectWarning`` — advertencia con acción sugerida.
"""
from django.core.exceptions import PermissionDenied, ValidationError

__all__ = ['ValidationError', 'UserError', 'AccessError', 'RedirectWarning']


class UserError(Exception):
    """Error de negocio mostrable al usuario (Odoo ``UserError``).

    Distinto de ``ValidationError`` (valida campo/constraint): interrumpe una
    operación por regla de negocio (p. ej. cancelar un asiento publicado).
    """


AccessError = PermissionDenied     # Odoo AccessError ≈ Django PermissionDenied


class RedirectWarning(Exception):
    """Advertencia con acción sugerida (Odoo ``RedirectWarning``)."""

    def __init__(self, message, action=None, button_text=None):
        super().__init__(message)
        self.action = action
        self.button_text = button_text
