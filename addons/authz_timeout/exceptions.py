"""Las dos denegaciones del candado por tiempo — ``addons.authz_timeout``.

Adaptación de ``CheckIdentityException`` de Odoo
``auth_timeout/models/ir_http.py:9-13`` (``odoo-tools@abe4040ec1``,
``odoo19c:``, LGPL-3) — atribución y aviso de licencia preservados
(DEC-KX-03).

La fuente declara **una** excepción y reusa ``SessionExpiredException`` del
núcleo para el otro desenlace. Aquí son dos clases porque este árbol no tiene
``SessionExpiredException``: su equivalente es el 401 que DRF ya emite cuando
no hay sesión, y el candado necesita distinguirlo del 403 de confirmar
identidad.

.. list-table::
   :header-rows: 1
   :widths: 34 32 34

   * - Desenlace de ``_must_check_identity``
     - En la fuente
     - Aquí
   * - ``{"logout": True}``
     - ``SessionExpiredException``
     - ``SessionLockExpired`` — 401
   * - ``{"check_identity": True}``
     - ``CheckIdentityException``
     - ``CheckIdentityRequired`` — 403

**Por qué no se reusa ``ReauthRequired``.** Los dos ejes son ortogonales y ya
lo declara el manifiesto de este addon: ``authz_reauth`` es step-up **por
acción** (esta acción es sensible) y ``authz_timeout`` es candado **por
tiempo** (pasó el umbral, sin importar la acción). Un cliente que reciba
``REAUTH_REQUIRED`` sabe qué acción reintentar; uno que reciba
``CHECK_IDENTITY_REQUIRED`` tiene que confirmar identidad para **seguir
usando la sesión**. Colapsarlos haría indistinguibles dos flujos con
recuperación distinta.

``loglevel`` de la fuente
=========================

La fuente fija ``loglevel = logging.DEBUG`` en ``CheckIdentityException`` con
su razón escrita: *"To log only with debug level in odoo/http.py
Application.__call__"*. Aquí el atributo se conserva **y tiene receptor**: lo
lee ``models/ir_http.py::_handle_error`` al emitir su registro, en vez de un
despachador central de la aplicación.
"""
import logging

from rest_framework.exceptions import APIException

#: Ruta del endpoint que recibe el formulario de confirmación de identidad
#: — ≙ ``/auth-timeout/session/check-identity`` (``controllers/main.py:15``).
CHECK_IDENTITY_URL = '/api/v2/authz/timeout/check-identity/'


class CheckIdentityRequired(APIException):
    """403 ``CHECK_IDENTITY_REQUIRED`` — ≙ ``CheckIdentityException`` (``:9``).

    Lleva en el cuerpo lo que el cliente necesita para abrir el diálogo sin
    una segunda llamada: la ruta a la que enviar la credencial, si hace falta
    un segundo factor, y qué métodos admite este usuario.
    """

    status_code = 403
    default_code = 'check_identity_required'

    #: ≙ ``loglevel`` (``:12``) — el candado que vence es operación normal, no
    #: un incidente; se registra en DEBUG.
    loglevel = logging.DEBUG

    def __init__(self, auth_methods=None, mfa=False):
        super().__init__(detail={
            'detail': 'Confirma tu identidad para continuar.',
            'codigo_error': 'CHECK_IDENTITY_REQUIRED',
            'check_identity_url': CHECK_IDENTITY_URL,
            'mfa': bool(mfa),
            'auth_methods': list(auth_methods or []),
        })


class SessionLockExpired(APIException):
    """401 ``SESSION_LOCK_EXPIRED`` — ≙ el ``SessionExpiredException`` que la
    fuente levanta en la rama ``logout`` (``ir_http.py:170``).

    Es 401 y no 403 porque la sesión ya no sirve: el cliente vuelve a
    autenticarse desde cero, no confirma identidad sobre la sesión vigente.
    """

    status_code = 401
    default_code = 'session_lock_expired'

    #: Mismo criterio que arriba: vencer el candado absoluto es operación
    #: normal.
    loglevel = logging.DEBUG

    def __init__(self):
        super().__init__(detail={
            'detail': 'Tu sesión alcanzó su duración máxima. Inicia sesión de nuevo.',
            'codigo_error': 'SESSION_LOCK_EXPIRED',
        })
