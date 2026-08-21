"""Lo que el candado por tiempo cuelga del usuario.

Adaptación de Odoo ``auth_timeout/models/res_users.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 51 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Porte símbolo por símbolo — 3 de 3 defs
=======================================

.. list-table::
   :header-rows: 1

   * - Símbolo (línea en la referencia)
     - Estado
   * - ``_inherit = "res.users"`` (``:5``)
     - portado — lo expresa ``extend_model('base', 'ResUsers', …)``
   * - ``_get_auth_methods`` (``:7``)
     - portado; **su cuerpo depende de ``_mfa_type``**, que no está en este
       árbol — ver el bloqueo medido abajo
   * - ``_get_lock_timeouts`` (``:26``)
     - portado
   * - ``_get_lock_timeout_inactivity`` (``:39``)
     - portado

Bloqueo medido — ``_mfa_type``
==============================

``_get_auth_methods`` llama a ``self._mfa_type()``, que **no existe aquí**
(medido: 2 hits en el árbol, ambos en prosa de
``addons/authz_totp_mail/models/res_users.py``; 0 definiciones). Su hogar en
la referencia **no es este addon** sino ``auth_totp/models/res_users.py``
(``:118-128``), un archivo de 19 defs — portarlo aquí sería declarar un
símbolo en sitio divergente, que es el defecto de :ref:`h-api-578`.

Las piezas para construirlo sí están (``user.totp_secret`` con ``confirmed``,
y ``totp_mail_required`` de ``authz_totp_mail``), así que es trabajo acotado y
no una incógnita. Sucesor registrado: tarea **#713**.

Mientras tanto ``_get_auth_methods`` levanta ``AttributeError`` si se invoca —
ruidoso a propósito. Su único consumidor en la referencia es la pantalla de
confirmación de identidad (``ir_http.py:96``), que este pase tampoco porta.

Divergencia declarada — ``_get_group_ids``
==========================================

La referencia resuelve los grupos del usuario con ``self._get_group_ids()``,
y su comentario dice por qué: *"Take advantage of the ormcache of
``self._get_group_ids()``"*. Ese método es del núcleo de ``res.users``, no de
este addon, y aquí no existe (medido: 1 hit, en prosa de
``src/addons/base/models/ir_ui_menu.py:121``). El acceso equivalente es el
reverso del M2M, ``user.group_ids``
(``src/addons/base/models/res_groups.py:164-166``) — misma población, sin la
caché que aquí no aplica porque la caché está un nivel más adentro, en
``ResGroups._get_lock_timeouts``.
"""
from django.apps import apps as django_apps

from orm.model_classes import extend_model


def _get_auth_methods(self):
    """≙ ``_get_auth_methods`` (``:7-24``).

    Los métodos de autenticación disponibles para el usuario: passkey
    (WebAuthn), segundo factor (app o correo) y contraseña, según lo que
    tenga configurado y la política de MFA.

    BLOQUEADO por ``_mfa_type`` — ver el docstring del módulo, sucesor #713.
    """
    auth_methods = []
    if self.passkeys.exists():
        auth_methods.append('webauthn')
    if mfa_type := self._mfa_type():
        auth_methods.append(mfa_type)
    auth_methods.append('password')
    return auth_methods


def _get_lock_timeouts(self):
    """≙ ``_get_lock_timeouts`` (``:26-38``).

    Delega en el nivel de grupo, usando la pertenencia del usuario para
    decidir qué umbrales aplican.
    """
    ResGroups = django_apps.get_model('base', 'ResGroups')
    return ResGroups._get_lock_timeouts(
        list(self.group_ids.values_list('pk', flat=True)))


def _get_lock_timeout_inactivity(self):
    """≙ ``_get_lock_timeout_inactivity`` (``:39-51``).

    El umbral de inactividad más corto que aplica al usuario, en segundos, o
    ``None`` si ningún grupo lo configura.
    """
    timeouts = self._get_lock_timeouts()
    inactivity = timeouts.get('lock_timeout_inactivity')
    return inactivity[0][0] if inactivity else None


def apply_authz_timeout_res_users_extensions():
    """Cuelga sobre ``res.users`` lo que el candado por tiempo le añade — ≙
    ``_inherit``."""
    extend_model('base', 'ResUsers', metodos={
        '_get_auth_methods': _get_auth_methods,
        '_get_lock_timeouts': _get_lock_timeouts,
        '_get_lock_timeout_inactivity': _get_lock_timeout_inactivity,
    })
