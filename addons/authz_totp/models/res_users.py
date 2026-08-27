"""Lo que el segundo factor por app cuelga del usuario — el eslabón medio.

Adaptación de Odoo ``auth_totp/models/res_users.py`` (``odoo-tools@622ddc2a``,
``odoo19c:``, LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

El eslabón MEDIO de una cadena de tres
======================================

La referencia declara ``_mfa_type`` y ``_mfa_url`` tres veces, y cada override
consulta ``super()`` **primero**::

    base (None) → auth_totp ('totp') → auth_totp_mail ('totp_mail')

Aquí eso se expresa con ``combine=keep_previous``: el eslabón interno gana, que
es la precedencia de la fuente. Un usuario con la app configurada **y** la
política de correo activa obtiene ``'totp'``, no ``'totp_mail'``. Sin ese
``combine`` la cadena daría el valor contrario y ningún gate lo vería — los dos
son valores válidos del mismo vocabulario. Ver ``orm.method_chain.keep_previous``.

Porte símbolo por símbolo — los 24 de la fuente y dónde vive cada uno
=====================================================================

El archivo de la referencia declara 5 atributos de clase y 19 métodos. Este
módulo aporta 3; el resto ya tenía hogar en el addon o está bloqueado con su
sucesor nombrado. Ninguno se omite en silencio
(``porte-completo-no-parcial.md``).

.. list-table::
   :header-rows: 1

   * - Símbolo de la referencia
     - Dónde vive aquí
   * - ``_inherit = 'res.users'``
     - ``extend_model('base', 'ResUsers', …)`` de este módulo
   * - ``totp_secret`` (Char ``NO_ACCESS``)
     - ``totp_secret.py`` — tabla lateral ``OneToOne``, divergencia declarada
   * - ``totp_last_counter`` (Integer ``NO_ACCESS``)
     - **NO portado** — es la anti-repetición del código; ver abajo
   * - ``totp_enabled`` (Boolean compute)
     - ``property`` de este módulo, delegando en ``services.totp_enabled``
   * - ``totp_trusted_device_ids`` (One2many)
     - ``totp_trusted_devices`` — el reverso de la FK que declara
       ``auth_totp.py``. En Django el One2many no se declara: es el
       ``related_name`` del lado Many2one
   * - ``init`` (``:38``)
     - divergencia de mecanismo: la columna la crea una migración de Django
   * - ``SELF_READABLE_FIELDS`` (``:44``)
     - **NO portado** — ``base.ResUsers`` no declara la lista blanca que extiende
   * - ``_mfa_type`` (``:47``)
     - **aquí**, encadenado con ``keep_previous``
   * - ``_mfa_url`` (``:54``)
     - **aquí**; la ruta es config L2, no la del backoffice
   * - ``_compute_totp_enabled`` (``:62``)
     - **aquí**, como ``property`` — ≙ el ``compute`` sin ``store``
   * - ``_rpc_api_keys_only`` (``:66``)
     - **NO portado** — bloqueo medido, ver abajo
   * - ``_get_session_token_fields`` (``:71``)
     - **NO portado** — el token de sesión de este árbol no se compone por campos
   * - ``_check_credentials`` (``:74``)
     - **aquí**, encadenado con el relevo por defecto; delega en
       ``services.verify_code``, que lleva la guarda del contador — ver abajo
   * - ``_totp_try_setting`` (``:98``)
     - ``services.confirm_setup``
   * - ``_totp_rate_limit`` / ``_totp_rate_limit_purge`` (``:120``, ``:145``)
     - **NO portados** — ``auth_totp_rate_limit_log``, gap nombrado en H-API-232
   * - ``action_totp_disable`` (``:155``)
     - ``services.disable`` + ``controllers.main.totp_disable``
   * - ``action_totp_enable_wizard`` (``:182``)
     - ``services.begin_setup`` + ``controllers.main.totp_setup``
   * - ``revoke_all_devices`` / ``_revoke_all_devices`` (``:208``, ``:211``)
     - ``auth_totp.revoke_all_devices`` — **una** función, no dos: la identidad
       fresca que allá pone ``@check_identity`` la exige aquí la vista
       (DEC-12), así que los dos cuerpos coinciden
   * - ``change_password`` (``:215``)
     - divergencia de mecanismo: su cuerpo entero es revocar y delegar en
       ``super()``; el cambio de contraseña vive en ``authz`` y llama a
       ``auth_totp.revoke_all_devices``
   * - ``_compute_totp_secret`` / ``_inverse_token`` (``:219``, ``:227``)
     - divergencia de mecanismo: el secreto es una fila, no un campo calculado
   * - ``_totp_enable_search`` (``:233``)
     - divergencia de mecanismo: se busca por ``totp_secret__confirmed=True``

Bloqueo medido — ``_rpc_api_keys_only``
=======================================

La referencia lo usa para negar el acceso RPC por contraseña cuando hay 2FA
(``odoo/addons/base/models/res_users.py:356,396`` son sus dos consumidores).
Este árbol **no tiene el canal que restringiría**: las claves de API para
integración externa no están construidas, y su porte es la tarea **#490**. Un
método que niega el acceso a un canal inexistente no niega nada — sería un
símbolo muerto con nombre de guarda, que es peor que su ausencia.

Se porta cuando exista el canal; su eslabón base tampoco se declaró en
``src/addons/base/models/res_users.py`` por la misma razón. Sucesor: **#490**.

Divergencia declarada — dónde vive el secreto
==============================================

La referencia guarda ``totp_secret`` como campo ``NO_ACCESS`` sobre
``res.users``; aquí vive en ``TotpSecret``, una tabla lateral ``OneToOne``
(``totp_secret.py``, decisión previa de este addon). ``totp_enabled`` se deriva
igual —el secreto existe **y** está confirmado— pero la lectura cruza una FK en
vez de leer una columna del propio usuario.

``totp_last_counter`` es anti-repetición, no metadato — CERRADO (#718)
=======================================================================

La fuente guarda el contador del último código aceptado y lo compara al
verificar (``:84-88``): ``if sudo.totp_last_counter and match <=
sudo.totp_last_counter: raise AccessDenied("please use the latest 6-digit
code")``. Sin él, un código capturado se vuelve a presentar dentro de su
ventana de ~90 s.

Portado en los **cuatro** puntos que la fuente toca, no sólo en la
comprobación: ``TotpSecret.last_counter`` guarda el intervalo;
``services.verify_code`` lo exige y lo asienta (``:84-88``);
``services.confirm_setup`` asienta el del código de alta (``:110``), que si no
serviría además para el primer login; y ``services.begin_setup`` lo reinicia al
cambiar el secreto (≙ ``_inverse_token``, ``:228``), porque el contador es del
secreto viejo.

El nombre pierde el prefijo ``totp_`` por la misma razón que ``totp_secret`` es
``secret``: allá los dos cuelgan de ``res.users`` y el prefijo desambigua; aquí
los dos viven en ``TotpSecret``.
"""
from exceptions import AccessDenied
from orm.method_chain import chain_method, keep_previous
from orm.model_classes import extend_model

from addons.authz_totp import services

# ≙ la ruta del segundo paso. En la referencia es del backoffice
# ('/web/login/totp', res_users.py:59); aquí es config L2 para que cada
# despliegue apunte a su ruta del SPA, mismo criterio que PARAM_INVITE_URL
# de authz_totp_mail.
TOTP_SECOND_STEP_URL = '/login/totp'


def totp_enabled(self):
    """≙ ``_compute_totp_enabled`` (``:62-64``) — ``bool(totp_secret)``.

    Delega en ``services.totp_enabled``, que ya era la implementación del
    addon: dos cuerpos con la misma pregunta serían dos fuentes de verdad que
    nadie sincroniza. Aquí el secreto vive en tabla lateral, así que además de
    existir tiene que estar **confirmado** — la fila nace con
    ``confirmed=False`` al empezar el alta y sólo pasa a ``True`` cuando el
    usuario verifica su primer código.
    """
    return services.totp_enabled(self)


def _mfa_type(self):
    """≙ ``_mfa_type`` (``:47-52``) — ``'totp'`` si la app está configurada.

    Devuelve ``None`` cuando no lo está: es el relevo que deja responder al
    siguiente eslabón de la cadena.
    """
    if self.totp_enabled:
        return 'totp'


def _mfa_url(self):
    """≙ ``_mfa_url`` (``:54-59``) — la ruta del segundo paso para ``'totp'``."""
    if self._mfa_type() == 'totp':
        return TOTP_SECOND_STEP_URL


def _check_credentials(self, credential, env):
    """≙ ``_check_credentials`` tipo ``totp`` (``:74-96``).

    Atiende su tipo y **devuelve ``None`` para cualquier otro**, que es el
    relevo perezoso de ``chain_method`` ocupando el lugar del
    ``return super()._check_credentials(...)`` de la fuente.

    ``mfa='default'`` es de la referencia y **no** es cosmético: su consumidor
    en el candado por tiempo compara ``auth['mfa'] != 'skip'`` para decidir si
    exige el segundo factor. Con ``'skip'`` esa rama no dispara y la
    confirmación de dos factores colapsa a uno — el defecto que este porte
    corrige (:ref:`h-api-780`).

    Los dos rechazos que ``services.verify_code`` distingue en el registro
    —código inválido y código ya usado— salen aquí como el mismo
    ``AccessDenied``, igual que en la fuente: decir cuál fue le confirmaría al
    atacante que el código era bueno.
    """
    if credential.get('type') != 'totp':
        return None
    if not services.verify_code(self, credential.get('token') or ''):
        raise AccessDenied(
            'Verification failed, please double-check the 6-digit code')
    return {'uid': self.pk, 'auth_method': 'totp', 'mfa': 'default'}


def _chain_mfa(model):
    """Instala los tres de la cadena con su ``combine``.

    Va por ``luego=`` y no por ``metodos=`` porque ``extend_model`` no expone
    ``combine``, y el relevo por defecto daría la precedencia contraria a la de
    la referencia.

    ``_check_credentials`` es la excepción: **sí** quiere el relevo por
    defecto, porque su semántica en la fuente es la del relevo —cada eslabón
    atiende su tipo y delega el resto—, no la de ``keep_previous``.
    """
    chain_method(model, '_mfa_type', _mfa_type, combine=keep_previous)
    chain_method(model, '_mfa_url', _mfa_url, combine=keep_previous)
    chain_method(model, '_check_credentials', _check_credentials)


def apply_authz_totp_res_users_extensions():
    """Cuelga sobre ``res.users`` lo que el 2FA por app le añade — ≙ ``_inherit``.

    ``keep_previous`` da la precedencia al eslabón anterior, que es la de la
    fuente: ``base`` calla y este addon responde, pero cuando
    ``authz_totp_mail`` se instale encima —depende de éste, así que va
    después— el suyo cederá ante este ``'totp'``.
    """
    extend_model('base', 'ResUsers', propiedades={
        'totp_enabled': totp_enabled,
    })
    extend_model('base', 'ResUsers', luego=_chain_mfa)
