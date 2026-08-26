"""``auth_totp.device`` — el dispositivo de confianza del segundo factor.

Portación de ``odoo19c: auth_totp/models/auth_totp.py`` (LGPL-3,
``odoo-tools@abe4040ec1``) — atribución y aviso de licencia preservados
(DEC-KX-03).

Qué es, con las palabras de la fuente
======================================

El comentario que abre la clase en la referencia explica por qué el modelo
existe en vez de reusar la tabla de claves de API::

    # init is overriden in res.users.apikeys to create a secret column 'key'
    # use a different model to benefit from the secured methods while not mixing
    # two different concepts

Es decir: **el mecanismo es el mismo, los conceptos no**. Una clave de API
autentica a una integración externa; un dispositivo de confianza recuerda que
este navegador ya presentó el segundo factor, y su clave viaja en la cookie
``td_id``. Compartir tabla haría que revocar una cosa revocara la otra.

Cómo se materializa aquí — herencia por prototipo
==================================================

La fuente lo obtiene con ``_name`` propio **más** ``_inherit``, que en su ORM
es herencia por **prototipo**: copia campos y métodos, tabla aparte. Aquí eso
es la base abstracta ``_ResUsersApikeysBase``
(``src/addons/base/models/res_users.py``), que se creó en este mismo pase
justo para esto y cuyo docstring lleva las cuatro divergencias del mecanismo.

Los métodos heredados son ``classmethod``, así que ``cls`` es **este** modelo:
``AuthTotpDevice._generate(...)`` escribe en ``auth_totp_device`` y
``AuthTotpDevice._check_credentials(...)`` sólo mira esa tabla. Es el mismo
reparto que la fuente logra pasando el nombre de tabla a
``_check_apikey_credentials``, y la razón por la que un dispositivo de
confianza **no** vale como clave de RPC.

Porte símbolo por símbolo — 2 de 2 defs, 4 de 4 atributos de clase
===================================================================

.. list-table::
   :header-rows: 1

   * - Símbolo (línea en la referencia)
     - Estado
   * - ``_name = 'auth_totp.device'`` (``:15``)
     - portado verbatim
   * - ``_inherit = ["res.users.apikeys"]`` (``:16``)
     - portado verbatim; su forma efectiva es la base abstracta
   * - ``_description = "Authentication Device"`` (``:17``)
     - portado verbatim
   * - ``_auto = False`` (``:18``)
     - portado verbatim — la tabla la gestiona Django (misma divergencia 1 que
       el padre)
   * - ``_check_credentials_for_uid`` (``:20``)
     - portado como ``classmethod``, igual que el ``_check_credentials`` que
       consume
   * - ``_get_trusted_device_age`` (``:25``)
     - portado como ``classmethod``; ``authz_timeout`` lo estrecha

Divergencia declarada — dónde viven las dos constantes
=======================================================

La referencia declara ``TRUSTED_DEVICE_COOKIE`` y ``TRUSTED_DEVICE_AGE_DAYS``
en ``auth_totp/controllers/home.py:11-12`` y las **importa hacia arriba**
desde el modelo. Aquí esa dirección cierra un ciclo de imports real, medido en
este árbol::

    models/auth_totp.py → controllers/main.py → services.py → models/

En la fuente no lo cierra porque su controlador no importa modelos: los pide
al registro del ORM por nombre (``request.env['auth_totp.device']``), que es un
mecanismo que este árbol no tiene. Así que las dos constantes se declaran
**aquí**, junto a su único consumidor, y el controlador que ponga la cookie las
importa de este módulo. Una sola declaración; sólo se invierte la dirección.
"""
import logging

from django.apps import apps as django_apps
from django.db.models import F
from django.db.models.functions import Length
from django.db.models.lookups import Exact

import fields
import models

from addons.base.models.res_users import (
    INDEX_SIZE,
    _ResUsersApikeysBase,
    index_name_for,
)
from orm.environments import get_current_user

_logger = logging.getLogger(__name__)

#: ≙ ``TRUSTED_DEVICE_COOKIE`` (``odoo19c:
#: auth_totp/controllers/home.py:11``) — el nombre de la cookie que lleva la
#: clave del dispositivo.
TRUSTED_DEVICE_COOKIE = 'td_id'

#: ≙ ``TRUSTED_DEVICE_AGE_DAYS`` (``:12``) — cuánto dura la confianza si nadie
#: la acorta. Es el valor por defecto del parámetro
#: ``auth_totp.trusted_device_age``.
TRUSTED_DEVICE_AGE_DAYS = 90

#: ≙ ``scope="browser"``, el ámbito con que se genera y se comprueba la clave
#: del dispositivo de confianza.
#:
#: **La fuente no declara esta constante**: escribe el literal en los TRES
#: sitios que lo usan — ``auth_totp/controllers/home.py:35,71`` (comprobar y
#: generar) y ``auth_totp_mail/models/res_users.py:57`` (el aviso de conexión
#: nueva). Aquí se declara una vez porque generar con un ámbito y comprobar
#: con otro es un **fallo silencioso**: la clave existe, la comprobación
#: devuelve ``None``, y el segundo factor se vuelve a pedir sin que nada lo
#: reporte. Vive junto a ``TRUSTED_DEVICE_COOKIE`` —el otro dato que los tres
#: comparten— y no en el controlador, porque el tercer consumidor está en otro
#: addon y no puede importar un símbolo privado de una vista.
BROWSER_SCOPE = 'browser'


class AuthTotpDevice(_ResUsersApikeysBase):
    """``auth_totp.device`` — ≙ ``Auth_TotpDevice`` (``:9-38``)."""

    _name = 'auth_totp.device'
    #: La referencia declara la herencia por prototipo sobre la clave de API.
    #: Se conserva **verbatim** como declaración de procedencia; su forma
    #: efectiva es heredar de ``_ResUsersApikeysBase``.
    _inherit = ['res.users.apikeys']
    _description = 'Authentication Device'
    #: Heredado de la clave de API, y por la misma razón: allá la tabla se
    #: emite a mano. Aquí la gestiona Django.
    _auto = False

    user = fields.Many2one(
        'base.ResUsers', on_delete=models.CASCADE, db_index=True,
        related_name='totp_trusted_devices',
        help_text='Odoo user_id — el dueño del dispositivo de confianza.',
    )

    class Meta:
        db_table            = 'auth_totp_device'
        ordering            = ['-id']
        verbose_name        = 'Dispositivo de confianza'
        verbose_name_plural = 'Dispositivos de confianza'
        indexes = [
            # El ``init()`` de la clave de API usa ``%(table)s``, así que el
            # hijo por prototipo crea el mismo índice sobre SU tabla. El nombre
            # sigue la convención de la fuente, con su rama de truncamiento
            # incluida — ver ``index_name_for``.
            models.Index(fields=['user', 'index'],
                         name=index_name_for('auth_totp_device')),
        ]
        constraints = [
            # Misma forma que el padre, y por la misma razón: Django no
            # registra ``__length`` como lookup de ``CharField``, así que el
            # ``char_length`` de la fuente se emite con ``Exact`` sobre
            # ``Length``.
            models.CheckConstraint(
                condition=Exact(Length(F('index')), INDEX_SIZE),
                name='auth_totp_device_index_size',
                violation_error_code='TRUSTED_DEVICE_INDEX_SIZE',
            ),
        ]

    @classmethod
    def _check_credentials_for_uid(cls, *, scope, key, uid):
        """≙ ``_check_credentials_for_uid`` (``:20-23``).

        Su docstring de la fuente, verbatim: *"Return True if device key
        matches given ``scope`` for user ID ``uid``"*.

        La comprobación de ``uid`` **no es redundante** con la de
        ``_check_credentials``: aquélla dice de quién es la clave, ésta exige
        que sea de quien dice el flujo de login. Sin ella, una cookie válida de
        otro usuario pasaría el segundo factor del usuario que se está
        autenticando.
        """
        assert uid, 'uid is required'
        return cls._check_credentials(scope=scope, key=key) == uid

    @classmethod
    def _get_trusted_device_age(cls):
        """≙ ``_get_trusted_device_age`` (``:25-37``) — la duración, en segundos.

        Lee ``auth_totp.trusted_device_age`` del parámetro de sistema y cae al
        default ante los **dos** modos de fallo que la fuente distingue con el
        mismo desenlace: un valor no numérico (``ValueError``) y uno ``<= 0``.
        El aviso también es el de la fuente — un parámetro mal puesto degrada a
        90 días en silencio salvo por esta línea del registro.

        ``sudo()`` no tiene receptor aquí: el parámetro de sistema no está
        gateado por capacidad al leerlo.
        """
        icp = django_apps.get_model('base', 'SystemParameter')
        try:
            nbr_days = int(icp.get_param('auth_totp.trusted_device_age',
                                         TRUSTED_DEVICE_AGE_DAYS))
            if nbr_days <= 0:
                nbr_days = None
        except (TypeError, ValueError):
            nbr_days = None

        if nbr_days is None:
            _logger.warning(
                "Invalid value for 'auth_totp.trusted_device_age', "
                "using default value.")
            nbr_days = TRUSTED_DEVICE_AGE_DAYS

        return nbr_days * 86400  # segundos


def revoke_all_devices(user=None):
    """≙ ``_revoke_all_devices`` (``:209-210``) — retira los dispositivos de un usuario.

    La fuente declara **dos** métodos sobre ``res.users``: el público
    ``revoke_all_devices`` con ``@check_identity`` y el interno
    ``_revoke_all_devices`` sin él. Aquí la identidad fresca la exige
    ``authz_reauth.assert_session_fresh`` desde la vista (DEC-12), así que la
    distinción no tiene dos cuerpos que separar: queda **una** función, y el
    gate lo pone quien la exponga.

    Es también el cuerpo entero de ``change_password`` (``:213-216``), que en
    la fuente sólo revoca y delega en ``super()``: aquí el cambio de contraseña
    vive en ``authz`` y llama a esta función.

    :param user: el usuario; por defecto, el de la petición en curso.
    """
    actor = user if user is not None else get_current_user()
    uid = getattr(actor, 'pk', None)
    if uid is None:
        return 0
    deleted, _rest = AuthTotpDevice.objects.filter(user_id=uid).delete()
    _logger.info("Trusted devices revoked for user #%s: %d", uid, deleted)
    return deleted
