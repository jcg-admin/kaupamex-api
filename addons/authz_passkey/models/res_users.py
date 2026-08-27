"""Lo que la passkey cuelga del usuario — el cuarto eslabón de la cadena.

Adaptación de Odoo ``auth_passkey/models/res_users.py`` (``odoo19c:``, LGPL-3) —
atribución y aviso de licencia preservados (DEC-KX-03).

Este archivo existe **porque la referencia lo declara aquí**. Hasta #722 su
contenido vivía repartido —el verificador en ``backends.py``, el despacho a
mano en ``authz_timeout``— y el mapa de ``__init__.py`` lo daba por absorbido.
Con la cadena de ``_check_credentials`` construida, el eslabón vuelve a su
sitio: la segunda cláusula de ``atributos-de-clase-de-modelo.md`` es que el
**hogar del archivo** también se lee contra la referencia, no sólo sus
símbolos.

Reparto de los cuatro símbolos de la fuente
============================================

.. list-table::
   :header-rows: 1

   * - Símbolo de la referencia
     - Dónde vive aquí
   * - ``_inherit = 'res.users'``
     - ``extend_model('base', 'ResUsers', luego=…)`` de este módulo
   * - ``auth_passkey_key_ids`` (One2many)
     - ``related_name='passkeys'`` de la FK que declara ``auth_passkey_key.py``.
       En Django el One2many no se declara: es el reverso del Many2one
   * - ``SELF_READABLE_FIELDS`` (``:17``)
     - **NO portado** — ``base.ResUsers`` no declara la lista blanca que extiende
   * - ``action_create_passkey`` (``:21``)
     - divergencia de mecanismo: la acción de ventana del backoffice es aquí el
       endpoint de registro (``../views.py``)
   * - ``_login`` (``:34``)
     - ``backends.PasskeyBackend.authenticate`` — el camino de login, con
       búsqueda global por ``credential_identifier``
   * - ``_check_credentials`` (``:49``)
     - **aquí**, encadenado; delega la búsqueda acotada y la verificación en
       ``backends.verify_webauthn_credential``
   * - ``_get_session_token_fields`` / ``_get_session_token_query_params``
       (``:74``, ``:77``)
     - **NO portados** — el token de sesión de Django no se deriva de campos
       del usuario; no hay qué extender

Divergencia declarada — ``request`` viaja en ``env``
====================================================

La fuente lee la petición de un hilo-local (su ``request`` global), así que su
``_check_credentials`` no la recibe. Aquí ``PasskeyKey._verify_auth`` la toma
explícita —el reto de WebAuthn vive en la sesión— y el único canal que la
cadena ofrece es ``env``. Por eso el llamador pasa
``{'interactive': True, 'request': request}`` y este eslabón lo lee de ahí.

Sin la petición no se puede leer el reto, así que su ausencia es un rechazo,
no un relevo: devolver ``None`` haría que la cadena delegara el tipo
``webauthn`` a un eslabón que no lo atiende, y el rechazo saldría con el
mensaje equivocado.
"""
from exceptions import AccessDenied
from orm.method_chain import chain_method
from orm.model_classes import extend_model

from addons.authz_passkey.models.backends import verify_webauthn_credential


def _check_credentials(self, credential, env):
    """≙ ``_check_credentials`` tipo ``webauthn`` (``:49-72``).

    Atiende su tipo y devuelve ``None`` para cualquier otro, que es el relevo
    perezoso de ``chain_method`` ocupando el lugar del
    ``return super()._check_credentials(...)`` de la fuente (``:71-72``).

    **La asimetría de ``auth_method`` es de la fuente y se copia verbatim:** el
    tipo de credencial es ``webauthn`` y el método devuelto es ``passkey``
    (``:69``). Ver :ref:`h-api-779`, que la midió al portar el otro camino.

    ``mfa='skip'`` también es suyo (``:70``), y aquí sí es correcto: una
    passkey autentica y verifica presencia en un solo gesto, así que **ya
    cuenta como los dos factores**. Es el único de los cuatro tipos que lo
    declara — los otros tres devuelven ``'default'`` para que el segundo factor
    se exija (:ref:`h-api-780`).

    El rechazo sale como ``AccessDenied``, igual que en la fuente (``:57``,
    ``:65``): ``verify_webauthn_credential`` devuelve ``None`` como contrato
    **interno** del verificador, y la traducción a la excepción se hace aquí,
    que es donde la referencia la levanta.
    """
    if credential.get('type') != 'webauthn':
        return None
    request = (env or {}).get('request')
    auth = verify_webauthn_credential(
        self, request, credential.get('webauthn_response'))
    if auth is None:
        # ≙ AccessDenied('Unknown passkey') y el AccessDenied de la aserción
        # inválida: la fuente no los distingue hacia fuera, y decir cuál fue le
        # confirmaría al atacante que la passkey existe.
        raise AccessDenied('Unknown passkey')
    return auth


def _chain_res_users(model):
    """Cuelga el eslabón de passkey sobre ``res.users``.

    Va **sin** ``combine``: el relevo por defecto de ``chain_method`` es
    exactamente la semántica de ``_check_credentials`` en la fuente — cada
    eslabón atiende su tipo y delega el resto.
    """
    chain_method(model, '_check_credentials', _check_credentials)


def apply_authz_passkey_res_users_extensions():
    """≙ ``_inherit = 'res.users'`` de la referencia (``:12``)."""
    extend_model('base', 'ResUsers', luego=_chain_res_users)
