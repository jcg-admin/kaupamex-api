"""Extensión LDAP del ciclo de credenciales del usuario.

Adaptación de Odoo ``auth_ldap/models/res_users.py`` (LGPL-3).

La referencia extiende ``res.users`` con ``_inherit``; Django no permite
inyectar métodos en el modelo de otra app, así que el archivo conserva el
**contenido** con la mecánica nativa equivalente:

- ``_login`` / ``_check_credentials`` (res_users.py:13-50) → ``../backends.py``
  (``LdapBackend``): la cadena ``AUTHENTICATION_BACKENDS`` ES la cadena de
  ``super()._login`` de Odoo — el backend de password local intenta primero y
  éste es el fallback, igual que el ``except AccessDenied`` de la referencia.
- ``change_password`` / ``_set_empty_password`` (res_users.py:52-69) → las
  funciones de este archivo, que el flujo de cambio de contraseña de cuenta
  (``account.password``) invoca antes de tocar el password local.
"""
import logging

from addons.authz_ldap.models.res_company_ldap import CompanyLdap

_logger = logging.getLogger(__name__)


def change_password(user, old_passwd, new_passwd):
    """≙ ``change_password`` (res_users.py:52-61).

    Si alguna configuración LDAP logra cambiar la contraseña en el
    directorio, el password local se vacía (la credencial vive en el
    directorio) y se devuelve ``True``. Si ninguna lo logra, devuelve
    ``False`` y el llamador continúa con el cambio de password local.

    Divergencia declarada: la referencia hace ``super().change_password``
    en el else; aquí el llamador (el endpoint de ``account.password``)
    decide el fallback — mismo orden, sin herencia.
    """
    if new_passwd:
        for conf in CompanyLdap.objects.get_ldap_dicts():
            changed = CompanyLdap._change_password(
                conf, user.login, old_passwd, new_passwd)
            if changed:
                set_empty_password(user)
                return True
    return False


def set_empty_password(user):
    """≙ ``_set_empty_password`` (res_users.py:63-69).

    La referencia pone ``password=NULL`` con SQL directo; el mecanismo
    nativo es ``set_unusable_password()`` — mismo efecto observable: el
    backend de password local nunca autentica a ese usuario y la credencial
    queda delegada al directorio.
    """
    user.set_unusable_password()
    user.save(update_fields=['password'])
