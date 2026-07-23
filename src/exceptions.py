"""Excepciones de la plataforma — fiel a ``odoo/exceptions.py`` (Odoo 18/19).

Módulo top-level (hermano de ``addons``, ``orm``, ``tools``, ``service``), con el
prefijo ``odoo.`` eliminado por la convención del proyecto (``pythonpath=src``):
igual que ``orm`` ≙ ``odoo/orm`` y ``tools`` ≙ ``odoo/tools``, aquí
``exceptions`` ≙ ``odoo/exceptions``. Un addon portado escribe ``from exceptions
import UserError, ValidationError``, leyendo como su fuente Odoo (``from
odoo.exceptions import UserError``).

Layout completo — las 9 clases de Odoo 19. Cada una lleva ``http_status`` como en
Odoo (el manejador de errores de DRF usa ``status_code``; se preserva
``http_status`` fiel para un handler que lo mapee).

Dos divergencias **deliberadas** de integración con Django (no se revierten: hay
código que las usa así):

- ``AccessError`` ≡ ``django.core.exceptions.PermissionDenied`` — para que el
  manejador de DRF devuelva **403** directo. En Odoo ``AccessError(UserError)``;
  aquí NO es subclase de ``UserError`` (un ``except UserError`` no lo captura).
- ``ValidationError`` ≡ ``django.core.exceptions.ValidationError`` — para que
  DRF/forms devuelvan **400** de validación de campo. En Odoo
  ``ValidationError(UserError)``; aquí es la de Django.

Las demás subclases (``AccessDenied``, ``MissingError``, ``LockError``) SÍ heredan
de nuestro ``UserError`` (fiel), así que ``except UserError`` sí las captura.
"""
from django.core.exceptions import PermissionDenied, ValidationError  # noqa: F401

__all__ = [
    'UserError', 'RedirectWarning', 'AccessDenied', 'AccessError', 'CacheMiss',
    'MissingError', 'LockError', 'ValidationError', 'ConcurrencyError',
]


class UserError(Exception):
    """Error de negocio mostrable al usuario (Odoo ``UserError``).

    Cuando el usuario intenta algo sin sentido dado el estado actual de un
    registro. Distinto de ``ValidationError`` (valida campo/constraint):
    interrumpe una operación por regla de negocio (p. ej. cancelar un asiento
    publicado).
    """
    http_status = 422  # Unprocessable Entity


class RedirectWarning(Exception):
    """Advertencia con acción sugerida (Odoo ``RedirectWarning``).

    :param message: mensaje mostrado al usuario.
    :param action: acción a la que redirigir.
    :param button_text: texto del botón que dispara la redirección.
    :param additional_context: contexto pasado a la acción.
    """

    def __init__(self, message, action=None, button_text=None,
                 additional_context=None):
        super().__init__(message, action, button_text, additional_context)
        self.action = action
        self.button_text = button_text
        self.additional_context = additional_context


class AccessDenied(UserError):
    """Error de login/contraseña (Odoo ``AccessDenied``).

    Traceback sólo visible en logs. Equivalente DRF: ``AuthenticationFailed``
    (401) — aquí se mantiene fiel como subclase de ``UserError`` con
    ``http_status`` 403, sin acoplar este módulo a ``rest_framework``.
    """
    http_status = 403  # Forbidden

    def __init__(self, message="Access Denied"):
        super().__init__(message)


# Odoo AccessError(UserError); aquí ≡ Django PermissionDenied → DRF 403 (divergencia).
AccessError = PermissionDenied


class CacheMiss(KeyError):
    """Valor(es) ausente(s) en el caché del ORM (Odoo ``CacheMiss``).

    En Django el caché de queries lo gestiona el propio ORM; se preserva por
    fidelidad de layout (rara vez la levanta código de aplicación).
    """

    def __init__(self, record, field):
        super().__init__("%r.%s" % (record, getattr(field, 'name', field)))


class MissingError(UserError):
    """Registro(s) ausente(s) (Odoo ``MissingError``).

    Al escribir sobre un registro borrado. Equivalente Django: ``Http404`` /
    ``Model.DoesNotExist``; se mantiene fiel como subclase de ``UserError``.
    """
    http_status = 404  # Not Found


class LockError(UserError):
    """Registro(s) que no se pudieron bloquear (Odoo ``LockError``).

    Cuando ``select_for_update`` no logra el lock. Relacionado con el reintento
    de concurrencia (``service/retry.py``).
    """
    http_status = 409  # Conflict


class ConcurrencyError(Exception):
    """Conflicto de concurrencia entre transacciones (Odoo ``ConcurrencyError``).

    Señala que la transacción fallida debe reintentarse tras un breve retardo;
    ver ``service/retry.py`` (el ``retrying`` de Odoo). Bajo nivel — la fuente
    real del deadlock 1213 de MariaDB es ``OperationalError`` de Django.
    """
