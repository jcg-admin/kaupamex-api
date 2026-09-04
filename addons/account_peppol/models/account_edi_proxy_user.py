"""``account_edi_proxy_client.user`` extendido por ``account_peppol``.

Adaptación de Odoo ``account_peppol/models/account_edi_proxy_user.py``
(``odoo19c: addons/account_peppol/models/account_edi_proxy_user.py``,
616 líneas, LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Qué es: el usuario del proxy EDI, especializado al tipo ``peppol``. El
transporte (firma HMAC/asimétrica, renovación de token, cifrado) ya lo trae
``addons/account_edi_proxy_client``; este archivo añade **el vocabulario
Peppol** encima: qué hosts, qué endpoints, cómo se traduce un error del proxy,
el ciclo de vida del participante y los cuatro crons.

Medido por AST en la fuente: 1 clase (``_inherit``), **1 campo**
(``proxy_type``, con ``selection_add``) y **32 métodos**.

Porte símbolo por símbolo — 33 símbolos: 21 portados, 12 bloqueados
=====================================================================

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Símbolo de la referencia (línea)
     - Desenlace
   * - ``proxy_type`` ``selection_add`` (``:22``)
     - **portado** — ``('peppol', 'PEPPOL')`` se añade a los ``choices`` del
       campo ya declarado, con el helper idempotente del árbol (divergencia 1).
   * - ``_get_peppol_proxy_types`` (``:29-30``)
     - **portado** como ``classmethod`` (divergencia 2).
   * - ``_get_proxy_urls`` (``:32-38``)
     - **portado** — encadenado con fusión de dict, porque la fuente hace
       ``urls = super(); urls['peppol'] = ...`` (divergencia 3).
   * - ``_get_peppol_proxy_endpoint`` (``:40-46``)
     - **portado** verbatim.
   * - ``_get_peppol_error_message`` (``:48-51``)
     - **portado** — la fuente lo marca ``DEPRECATED``; se conserva porque el
       porte es completo o declara su cobertura.
   * - ``_call_peppol_proxy`` (``:53-101``)
     - **portado** — las tres ramas de error (``no_such_user``,
       ``invalid_signature``, resto) y el ``error`` del cuerpo. Sin
       ``@handle_demo`` (ver ``tools/demo_utils.py``) y sin los ``cr.commit()``
       (divergencia 4).
   * - ``_mark_connection_out_of_sync`` (``:103-124``)
     - **portado**.
   * - ``_peppol_out_of_sync_reconnect_this_database`` (``:126-152``)
     - **portado** salvo el ``_trigger()`` del cron por identificador externo
       (divergencia 5).
   * - ``_peppol_out_of_sync_disconnect_this_database`` (``:154-160``)
     - **portado**.
   * - ``_get_can_send_domain`` (``:162-163``)
     - **portado** como ``classmethod`` — la tripleta verbatim.
   * - ``_cron_peppol_get_new_documents`` (``:169-171``)
     - **portado** como ``classmethod``; su cuerpo llama a
       ``_peppol_get_new_documents``, bloqueado, así que hoy es un no-op
       declarado (ver esa fila).
   * - ``_cron_peppol_get_message_status`` (``:173-175``)
     - ídem.
   * - ``_cron_peppol_get_participant_status`` (``:177-183``)
     - **portado** — sin el re-``_trigger()`` horario (divergencia 5).
   * - ``_cron_peppol_webhook_keepalive`` (``:185-187``)
     - **portado**.
   * - ``_get_proxy_identification`` (``:193-199``)
     - **portado** como ``classmethod``, encadenado sobre el del proxy client
       (que ya es ``classmethod``, ``addons/account_edi_proxy_client/models/
       account_edi_proxy_user.py:201``). BLOQUEADO su cuerpo Peppol: lee
       ``company.peppol_eas`` / ``company.peppol_endpoint``, campos de
       ``account_edi_ubl_cii`` (ver «La arista bloqueante» abajo). Se porta la
       forma con el error declarado.
   * - ``_peppol_get_filetype`` (``:320-321``)
     - **portado** verbatim.
   * - ``_peppol_get_decoded_document`` (``:323-326``)
     - **portado** — usa ``_decrypt_data`` del proxy client, que sí existe
       (``account_edi_proxy_user.py:335``).
   * - ``_peppol_process_participant_status`` (``:417-433``)
     - **portado** — el mapa de estados del proxy a los nuestros, verbatim.
   * - ``_peppol_get_participant_status`` (``:435-463``)
     - **portado** — incluida la asimetría de ``client_gone`` (baja) frente al
       resto de errores (sólo log).
   * - ``_peppol_register_sender_as_receiver`` (``:474-505``)
     - **portado** salvo el ``_trigger`` del cron (divergencia 5) y la lectura
       del ``selection`` traducido vía ``ir.model.fields`` (divergencia 6).
   * - ``_peppol_deregister_participant`` (``:507-532``)
     - **portado** sin ``@handle_demo`` ni ``cr.commit()``.
   * - ``_peppol_deregister_participant_to_sender`` (``:534-547``)
     - **portado**.
   * - ``_peppol_get_services`` (``:580-584``)
     - **portado**.
   * - ``_generate_webhook_token`` (``:586-591``)
     - **portado** — construido sobre ``django.core.signing``, porque
       ``tools.hash_sign`` no existe aquí (divergencia 7).
   * - ``_get_user_from_token`` (``:593-611``)
     - **portado**, con la misma verificación de que la URL empieza por el
       endpoint firmado, y el mismo *fallback* heredado.
   * - ``_peppol_reset_webhook`` (``:613-616``)
     - **portado**.
   * - ``_peppol_import_invoice`` (``:201-257``)
     - BLOQUEADO por ``account_edi_ubl_cii`` — importa el XML entrante con
       ``_get_edi_builder`` / el flujo de importación UBL de ese addon, que
       **se está portando en otro pase y no puede tocarse desde aquí**.
       Bloqueadores de segundo orden medidos: ``AccountJournal.is_self_billing``
       y ``AccountMove.is_sale_document`` → 0 hits en este árbol.
   * - ``_peppol_get_new_documents`` (``:259-318``)
     - BLOQUEADO — orquesta ``_peppol_import_invoice`` (arriba) y depende de
       ``company.peppol_purchase_journal_id`` y del identificador externo del
       cron.
   * - ``_peppol_process_new_messages`` (``:328-349``)
     - BLOQUEADO — crea ``ir.attachment`` con ``raw`` y llama a
       ``_peppol_import_invoice``.
   * - ``_peppol_post_process_new_messages`` (``:351-355``)
     - BLOQUEADO por ``AccountJournal._notify_einvoices_received`` (0 hits) y
       por ``button_account_peppol_check_partner_endpoint``, que a su vez
       depende de la arista ``account_edi_ubl_cii``.
   * - ``_peppol_get_message_status`` (``:357-383``) /
       ``_peppol_get_documents_for_status`` (``:385-394``) /
       ``_peppol_process_messages_status`` (``:396-415``)
     - BLOQUEADOS por ``AccountMove.peppol_move_state`` **en su forma de
       consulta**: el trío busca movimientos por ese campo y por
       ``sending_data``, y escribe el resultado del envío. Su hogar es el
       flujo de envío (``models/account_move_send.py``), bloqueado entero.
   * - ``_get_company_details`` (``:465-468``)
     - BLOQUEADO por ``peppol.registration`` — el modelo del asistente de
       alta, que la referencia declara en ``wizard/peppol_registration.py`` y
       aquí está bloqueado (ver ese archivo). La fuente además lo marca
       ``DEPRECATED``.
   * - ``_peppol_register_sender`` (``:470-472``)
     - no portado — cuerpo vacío en la fuente, marcado ``DEPRECATED``. Portar
       un método que no hace nada sólo añade superficie.
   * - ``_peppol_auto_register_services`` (``:549-552``)
     - no portado — ídem: ``pass``, marcado ``DEPRECATED``.
   * - ``_peppol_auto_deregister_services`` (``:554-578``)
     - BLOQUEADO por ``company._peppol_modules_document_types()`` **por
       módulo**: recorre los tipos de documento que aporta cada módulo
       instalado y los da de baja en el proxy; depende del registro de
       módulos de Odoo (``ir.module.module``) para saber cuál se está
       desinstalando.

La arista bloqueante — ``account_edi_ubl_cii``
================================================

Medido en la referencia: ``peppol_eas``, ``peppol_endpoint``,
``invoice_edi_format`` y ``EAS_MAPPING`` **los declara
``account_edi_ubl_cii``**, no ``account_peppol``
(``odoo19c: addons/account_edi_ubl_cii/models/res_partner.py:43,51`` y
``.../account_edi_common.py:52``). Ese addon se está portando **en paralelo,
en otro pase**, así que este addon **no lo importa ni lo declara en
``depends``**: cada símbolo que lo necesita queda marcado *BLOQUEADO por
``account_edi_ubl_cii``* y el orquestador reconcilia la arista al consolidar.

Divergencias declaradas
=========================

1. **``selection_add`` → ``_extend_selection_choices``.** El campo
   ``proxy_type`` ya existe (``choices=[]``, blanco por defecto); se le añade
   ``('peppol', 'PEPPOL')`` en sitio, sin migración y de forma idempotente —
   el helper que ``account/models/account_analytic_line.py:139`` ya usa. El
   ``ondelete={'peppol': 'cascade'}`` de la fuente describe qué hacer con las
   filas cuando se desinstala el módulo que aporta el valor; sin registro de
   módulos aquí, no tiene contraparte.
2. **``@api.model`` → ``@classmethod``.** Un método que la referencia marca
   ``@api.model`` no usa el registro: aquí es ``classmethod``, y **cada
   ``cls.X(...)`` de este archivo apunta a uno** (regla de coherencia de
   ``H-API-738``).
3. **``super()`` → ``chain_method`` con fusión de dict** para
   ``_get_proxy_urls``: la fuente muta el dict del padre; aquí cada eslabón
   devuelve sólo su aporte y ``combine`` funde.
4. **``self.env.cr.commit()`` cae.** La fuente commitea a media transacción
   para que el cambio de estado sobreviva al ``raise`` siguiente. Aquí no hay
   transacción abierta que cerrar salvo que el llamador la abra
   (``src/orm/environments.py``: ``env.cr`` → ``transaction.atomic``), así que
   el ``commit`` no tiene contraparte — misma omisión declarada que
   ``account_edi_proxy_client._make_request`` ya lleva escrita.
5. **Los ``_trigger()`` de cron caen.** Todos resuelven un identificador
   externo (``account_peppol.ir_cron_peppol_*``) que vive en ``data/cron.xml``
   de la referencia — XML de datos, no portado. Los métodos de cron **sí** se
   portan (son el trabajo); lo que falta es su programación declarativa.
   Sucesor: tarea PENDIENTE DE ASIGNAR — cablearlos a ``ir.cron`` cuando se
   porte la capa de datos del addon.
6. **``ir.model.fields.get_field_selection`` → los ``choices`` del campo.** La
   fuente pide la etiqueta traducida del estado al registro de campos; aquí se
   lee del ``choices`` de Django, que es la misma información.
7. **``tools.hash_sign`` / ``verify_hash_signed`` → ``django.core.signing``.**
   Medido: ``grep -rn "def hash_sign" src/tools/*.py`` → **0 hits**. El stack
   sí trae el mecanismo —firma con la ``SECRET_KEY`` y caducidad por
   antigüedad—, así que se construye con él en vez de aceptar la divergencia:
   ``dumps``/``loads`` con ``salt`` propio y ``max_age`` de 30 días, que es la
   misma expiración que la fuente declara (``expiration_hours=30 * 24``).
"""
import logging
from datetime import timedelta

from django.core import signing

from addons.account_edi_proxy_client.models.account_edi_proxy_user import (
    AccountEdiProxyError,
    AccountEdiProxyUser,
)
from addons.account_peppol.exceptions import get_peppol_error_message
from addons.account_peppol.tools.peppol_iap_connector import PEPPOL_PROXY_URLS
from exceptions import UserError
from orm.method_chain import chain_method
from orm.model_classes import extend_selection_choices
from tools.translate import _

_logger = logging.getLogger(__name__)

#: ≙ ``BATCH_SIZE`` (``odoo19c: :16``) — el tamaño de lote de los crons que
#: recorren documentos. Se conserva aunque sus consumidores estén bloqueados:
#: es parte del contrato del archivo.
BATCH_SIZE = 50

#: Caducidad del token de webhook, en horas — verbatim de
#: ``_generate_webhook_token`` (``odoo19c: :587``).
WEBHOOK_TOKEN_EXPIRATION_HOURS = 30 * 24

#: ``salt`` de la firma del webhook. Es la cadena que la fuente pasa a
#: ``hash_sign`` como ámbito (``'account_peppol_webhook'``), y cumple el mismo
#: papel: dos firmas de ámbitos distintos no se confunden.
WEBHOOK_SIGNING_SALT = 'account_peppol_webhook'


def _extend_selection_choices(model, field_name, extra_choices):
    """≙ ``selection_add=`` con su ``ondelete=`` — delega en el compartido.

    Era una copia local de :func:`orm.model_classes.extend_selection_choices`,
    una de cuatro idénticas en el árbol. Se retiran las cuatro: el compartido
    hace lo mismo **y** acepta el ``ondelete`` que la fuente declara junto al
    ``selection_add``, que es lo que la tarea **#205** construyó.

    La política es la medida en ``odoo19c: account_peppol/models/account_edi_proxy_user.py``:
    ``{'peppol': 'cascade'}``. Sin ella los registros que
    guardaban el valor quedaban huérfanos al borrarlo.
    """
    return extend_selection_choices(
        model, field_name, extra_choices,
        ondelete={'peppol': 'cascade'})
def _merge_with_previous(new, previous):
    """``combine`` para hooks que aportan claves a un dict — ≙
    ``urls = super()...; urls['peppol'] = ...``."""
    return {**(previous or {}), **(new or {})}


# -------------------------------------------------------------------------
# MÉTODOS DE APOYO
# -------------------------------------------------------------------------

def _get_peppol_proxy_types(cls):
    """≙ ``_get_peppol_proxy_types`` (``odoo19c: :29-30``) — los tipos de
    proxy que este addon reconoce como Peppol."""
    return ['peppol']


def _get_proxy_urls(self):
    """≙ ``_get_proxy_urls`` (``odoo19c: :32-38``) — publica los hosts Peppol.

    Devuelve SOLO el aporte propio; la fusión con lo que ya había la hace
    ``chain_method`` (divergencia 3).
    """
    return {
        'peppol': {
            **PEPPOL_PROXY_URLS,
            'demo': 'demo',
        },
    }


def _get_peppol_proxy_endpoint(self, endpoint, proxy_type=None):
    """≙ ``_get_peppol_proxy_endpoint`` (``odoo19c: :40-46``).

    El ``endpoint`` incluye el número de versión, p. ej. ``2/participant_status``.
    """
    if not proxy_type:
        proxy_type = self.proxy_type
    return f'/api/{proxy_type}/{endpoint}'


def _get_peppol_error_message(cls, error_vals):
    """≙ ``_get_peppol_error_message`` (``odoo19c: :48-51``). La fuente lo
    marca ``DEPRECATED``; se porta igual porque el porte es completo."""
    return get_peppol_error_message(error_vals)


def _get_can_send_domain(cls):
    """≙ ``_get_can_send_domain`` (``odoo19c: :162-163``) — los tres estados
    de empresa desde los que ya se puede enviar. Verbatim."""
    return ('sender', 'smp_registration', 'receiver')


# -------------------------------------------------------------------------
# LA LLAMADA AL PROXY
# -------------------------------------------------------------------------

def _call_peppol_proxy(self, endpoint, params=None):
    """≙ ``_call_peppol_proxy`` (``odoo19c: :53-101``) — la llamada firmada,
    con el tratamiento de error que la fuente define.

    Sin ``@handle_demo``: el arnés de demo está bloqueado y no se finge que
    exista (ver ``tools/demo_utils.py``). Sin ``cr.commit()``: divergencia 4.
    """
    peppol_proxy_types = type(self)._get_peppol_proxy_types()
    if self.proxy_type not in peppol_proxy_types:
        etiquetas = dict(type(self)._meta.get_field('proxy_type').choices)
        proxy_types = [etiquetas.get(tipo, tipo) for tipo in peppol_proxy_types]
        raise UserError(_(
            'El usuario EDI debe ser de alguno de estos tipos: %s',
            ' o '.join(proxy_types),
        ))

    token_out_of_sync_error_message = _(
        'Falló la conexión con el Access Point de Peppol. Puede ocurrir si '
        'restauró la base de datos desde un respaldo o la copió sin '
        'neutralizar. Para corregirlo, vaya a Configuración > Contabilidad > '
        'Peppol y presione «Reconectar esta base de datos».'
    )

    if self.is_token_out_of_sync:
        raise UserError(token_out_of_sync_error_message)

    params = params or {}
    try:
        response = self._make_request(f'{self._get_server_url()}{endpoint}', params=params)
    except AccountEdiProxyError as e:
        if (
            e.code == 'no_such_user'
            and not self.active
            and not self.company_id.account_edi_proxy_client_ids.filter(
                proxy_type=self.proxy_type,
            ).exists()
        ):
            self.company_id.account_peppol_proxy_state = 'not_registered'
            self.company_id.account_peppol_migration_key = ''
            self.company_id.save(update_fields=[
                'account_peppol_proxy_state', 'account_peppol_migration_key',
            ])
            raise UserError(_(
                'No encontramos un usuario con esta información en nuestro '
                'servidor. Verifique sus datos.'
            ))
        if e.code == 'invalid_signature':
            self._mark_connection_out_of_sync()
            raise UserError(token_out_of_sync_error_message)
        raise UserError(e.message)

    if error_vals := response.get('error'):
        raise UserError(get_peppol_error_message(error_vals))

    return response


# -------------------------------------------------------------------------
# TOKEN DESINCRONIZADO
# -------------------------------------------------------------------------

def _mark_connection_out_of_sync(self):
    """≙ ``_mark_connection_out_of_sync`` (``odoo19c: :103-124``)."""
    if self.is_token_out_of_sync:
        return
    self.is_token_out_of_sync = True
    self.refresh_token = ''
    self.save(update_fields=['is_token_out_of_sync', 'refresh_token'])

    try:
        self._make_request(
            f'{self._get_server_url()}/api/peppol/1/mark_connection_out_of_sync',
            params={'token_desync_counter': self.token_sync_version},
            auth_type='asymmetric',
        )
    except AccountEdiProxyError as e:
        if e.code == 'connection_superseded':
            self._peppol_out_of_sync_disconnect_this_database()
            raise UserError(_(
                'Otra base de datos reemplazó esta conexión. Regístrese de nuevo.'
            ))
        raise


def _peppol_out_of_sync_reconnect_this_database(self):
    """≙ ``_peppol_out_of_sync_reconnect_this_database`` (``odoo19c: :126-152``).

    Sin el ``_trigger()`` final del cron de estado del participante
    (divergencia 5): el identificador externo vive en ``data/cron.xml``.
    """
    assert self.is_token_out_of_sync
    self.token_sync_version += 1
    self.save(update_fields=['token_sync_version'])
    response = self._make_request(
        f'{self._get_server_url()}/api/peppol/1/resync_connection',
        params={'token_desync_counter': self.token_sync_version},
        auth_type='asymmetric',
    )
    if response.get('error'):
        if response['error'].get('code') == 'connection_superseded':
            self._peppol_out_of_sync_disconnect_this_database()
        raise AccountEdiProxyError(
            response['error'].get('code', 'unknown_error'),
            response['error'].get(
                'message',
                'Ocurrió un error desconocido al autenticarse con el servidor IAP.',
            ),
        )
    self.refresh_token = response['refresh_token']
    self.is_token_out_of_sync = False
    self.save(update_fields=['refresh_token', 'is_token_out_of_sync'])


def _peppol_out_of_sync_disconnect_this_database(self):
    """≙ ``_peppol_out_of_sync_disconnect_this_database`` (``odoo19c: :154-160``)."""
    assert self.is_token_out_of_sync
    self.company_id._reset_peppol_configuration(soft=True)
    self.delete()


# -------------------------------------------------------------------------
# CRONS
# -------------------------------------------------------------------------

def _cron_peppol_get_new_documents(cls):
    """≙ ``_cron_peppol_get_new_documents`` (``odoo19c: :169-171``).

    Su cuerpo llama a ``_peppol_get_new_documents``, BLOQUEADO por
    ``account_edi_ubl_cii`` — así que hoy selecciona a los usuarios y no hace
    nada más. Se porta la selección porque es el contrato del cron y no
    depende de la arista bloqueada.
    """
    return AccountEdiProxyUser.objects.filter(
        company__account_peppol_proxy_state='receiver',
        proxy_type__in=cls._get_peppol_proxy_types(),
    )


def _cron_peppol_get_message_status(cls):
    """≙ ``_cron_peppol_get_message_status`` (``odoo19c: :173-175``). Ídem —
    su consumidor ``_peppol_get_message_status`` está bloqueado."""
    return AccountEdiProxyUser.objects.filter(
        company__account_peppol_proxy_state__in=cls._get_can_send_domain(),
        proxy_type__in=cls._get_peppol_proxy_types(),
    )


def _cron_peppol_get_participant_status(cls):
    """≙ ``_cron_peppol_get_participant_status`` (``odoo19c: :177-183``).

    Sin el re-``_trigger()`` horario durante ``smp_registration``
    (divergencia 5).
    """
    for edi_user in AccountEdiProxyUser.objects.filter(
        proxy_type__in=cls._get_peppol_proxy_types(),
    ):
        edi_user._peppol_get_participant_status()


def _cron_peppol_webhook_keepalive(cls):
    """≙ ``_cron_peppol_webhook_keepalive`` (``odoo19c: :185-187``)."""
    for edi_user in AccountEdiProxyUser.objects.filter(
        company__account_peppol_proxy_state__in=['sender', 'receiver'],
    ):
        edi_user._peppol_reset_webhook()


# -------------------------------------------------------------------------
# IDENTIFICACIÓN
# -------------------------------------------------------------------------

def _get_proxy_identification(cls, company, proxy_type):
    """≙ ``_get_proxy_identification`` (``odoo19c: :193-199``).

    **BLOQUEADO en su cuerpo** por ``account_edi_ubl_cii``: la identificación
    Peppol es ``f'{company.peppol_eas}:{company.peppol_endpoint}'`` y esos dos
    campos los declara ese addon (``odoo19c: account_edi_ubl_cii/models/
    res_partner.py:43,51``), que se porta en otro pase. Se porta la **forma**
    —el despacho por ``proxy_type`` y el ``UserError`` con su texto— para que
    la cadena quede armada y sólo falte la lectura de los dos campos.

    ``classmethod`` porque el método que encadena ya lo es
    (``addons/account_edi_proxy_client/models/account_edi_proxy_user.py:201``).
    """
    if proxy_type == 'peppol':
        raise UserError(_(
            'Complete el código EAS y el identificador de participante. '
            '(Bloqueado por account_edi_ubl_cii: los campos peppol_eas y '
            'peppol_endpoint los aporta ese addon.)'
        ))
    return None


# -------------------------------------------------------------------------
# DOCUMENTOS ENTRANTES — la parte que no depende de la importación UBL
# -------------------------------------------------------------------------

def _peppol_get_filetype(self, content):
    """≙ ``_peppol_get_filetype`` (``odoo19c: :320-321``) — verbatim."""
    return 'xml', 'application/xml'


def _peppol_get_decoded_document(self, content):
    """≙ ``_peppol_get_decoded_document`` (``odoo19c: :323-326``).

    ``_decrypt_data`` lo trae el proxy client
    (``addons/account_edi_proxy_client/models/account_edi_proxy_user.py:335``).
    """
    return self._decrypt_data(content['document'], content['enc_key'])


# -------------------------------------------------------------------------
# ESTADO DEL PARTICIPANTE
# -------------------------------------------------------------------------

def _peppol_process_participant_status(self, proxy_user):
    """≙ ``_peppol_process_participant_status`` (``odoo19c: :417-433``).

    El mapa de estados del proxy a los nuestros, verbatim. ``draft`` del lado
    del proxy significa que allá ya no hay alta: se limpia la configuración y
    se archiva el usuario.
    """
    local_state = {
        'draft': 'not_registered',
        'sender': 'sender',
        'smp_registration': 'smp_registration',
        'receiver': 'receiver',
        'rejected': 'rejected',
    }.get(proxy_user.get('peppol_state'))

    if local_state == 'not_registered':
        self.company_id._reset_peppol_configuration()
        self.active = False
        self.save(update_fields=['active'])
    elif local_state:
        self.company_id.account_peppol_proxy_state = local_state
        self.company_id.save(update_fields=['account_peppol_proxy_state'])
    else:
        _logger.warning(
            "Estado Peppol desconocido '%s' para el usuario de proxy EDI id=%s",
            proxy_user.get('peppol_state'), self.pk,
        )


def _peppol_get_participant_status(self):
    """≙ ``_peppol_get_participant_status`` (``odoo19c: :435-463``).

    Es un método de cron: **traga** el ``AccountEdiProxyError``. La asimetría
    de la fuente se conserva — sólo ``client_gone`` da de baja la conexión;
    cualquier otro error se registra y ya, para no dejar al cliente en un
    estado del que no pueda salir sin intervención.
    """
    if self.proxy_type not in type(self)._get_peppol_proxy_types():
        return
    try:
        endpoint = self._get_peppol_proxy_endpoint('2/participant_status')
        proxy_user = self._make_request(f'{self._get_server_url()}{endpoint}')
    except AccountEdiProxyError as e:
        if e.code == 'client_gone':
            self.company_id._reset_peppol_configuration()
            self.active = False
            self.save(update_fields=['active'])
        else:
            _logger.error('Error al actualizar el estado del participante Peppol: %s', e)
        return

    if 'error' in proxy_user:
        error_message = (proxy_user['error'].get('message')
                         or proxy_user['error'].get('data', {}).get('message'))
        _logger.error('Error al actualizar el estado del participante Peppol: %s', error_message)
        return

    self._peppol_process_participant_status(proxy_user)


# -------------------------------------------------------------------------
# ALTA Y BAJA DEL PARTICIPANTE
# -------------------------------------------------------------------------

def _peppol_register_sender_as_receiver(self):
    """≙ ``_peppol_register_sender_as_receiver`` (``odoo19c: :474-505``).

    Un participante sólo puede pedir el alta como receptor si hoy es emisor.
    Sin el ``_trigger`` horario del cron (divergencia 5) y leyendo la etiqueta
    del estado de los ``choices`` del campo (divergencia 6).
    """
    company = self.company_id

    if company.account_peppol_proxy_state != 'sender':
        etiquetas = dict(type(company)._meta.get_field(
            'account_peppol_proxy_state',
        ).choices)
        raise UserError(_(
            'No se puede registrar un usuario con una solicitud %s',
            etiquetas.get(company.account_peppol_proxy_state,
                          company.account_peppol_proxy_state),
        ))

    edi_identification = type(self)._get_proxy_identification(company, 'peppol')
    peppol_info = company._get_company_info_on_peppol(edi_identification)
    if peppol_info['is_on_peppol']:
        company.peppol_external_provider = peppol_info['external_provider'] or ''
        company.save(update_fields=['peppol_external_provider'])
        raise UserError(peppol_info['error_msg'])

    self._call_peppol_proxy(
        endpoint=self._get_peppol_proxy_endpoint('1/register_sender_as_receiver'),
        params={
            'migration_key': company.account_peppol_migration_key,
            'supported_identifiers': list(company._peppol_supported_document_types()),
        },
    )
    # Una vez enviada la clave de migración ya no hace falta guardarla, pero el
    # campo se conserva por si el usuario decide migrar fuera de Odoo.
    company.account_peppol_migration_key = ''
    company.account_peppol_proxy_state = 'smp_registration'
    company.peppol_external_provider = ''
    company.save(update_fields=[
        'account_peppol_migration_key',
        'account_peppol_proxy_state',
        'peppol_external_provider',
    ])


def _peppol_deregister_participant(self):
    """≙ ``_peppol_deregister_participant`` (``odoo19c: :507-532``).

    Sin ``@handle_demo`` ni ``cr.commit()``. La recogida previa de documentos
    y estados —que la fuente hace para no perder acuses— llama a los dos crons
    cuyos consumidores están BLOQUEADOS (``_peppol_get_new_documents`` /
    ``_peppol_get_message_status``); se conserva la llamada porque su
    selección sí funciona y el día que caiga la arista el flujo queda entero.
    """
    proxy_state = None
    try:
        # Se llama a ``_make_request`` directo y no a
        # ``_peppol_get_participant_status``: aquél traga el error y aquí hace
        # falta distinguirlo (comentario verbatim de la fuente).
        endpoint = self._get_peppol_proxy_endpoint('2/participant_status')
        proxy_user = self._make_request(f'{self._get_server_url()}{endpoint}')
        proxy_state = proxy_user.get('peppol_state')
    except AccountEdiProxyError as e:
        if e.code not in ('client_gone', 'no_such_user_found'):
            raise

    if proxy_state in ('sender', 'smp_registration', 'receiver'):
        type(self)._cron_peppol_get_message_status()
        type(self)._cron_peppol_get_new_documents()
        self._call_peppol_proxy(
            endpoint=self._get_peppol_proxy_endpoint('1/cancel_peppol_registration'),
        )

    self.company_id._reset_peppol_configuration()
    self.delete()


def _peppol_deregister_participant_to_sender(self):
    """≙ ``_peppol_deregister_participant_to_sender`` (``odoo19c: :534-547``)
    — baja de receptor a emisor, conservando la conexión."""
    if self.company_id.account_peppol_proxy_state == 'receiver':
        type(self)._cron_peppol_get_message_status()
        type(self)._cron_peppol_get_new_documents()

    self._call_peppol_proxy(
        endpoint=self._get_peppol_proxy_endpoint('1/unregister_to_sender'),
    )
    self.company_id.account_peppol_proxy_state = 'sender'
    self.company_id.save(update_fields=['account_peppol_proxy_state'])


def _peppol_get_services(self):
    """≙ ``_peppol_get_services`` (``odoo19c: :580-584``)."""
    return self._call_peppol_proxy(self._get_peppol_proxy_endpoint('2/get_services'))


# -------------------------------------------------------------------------
# WEBHOOK
# -------------------------------------------------------------------------

def _generate_webhook_token(cls, company):
    """≙ ``_generate_webhook_token`` (``odoo19c: :586-591``).

    Firma ``[company.id, endpoint]`` con la clave de la instalación. Se
    construye con ``django.core.signing`` porque ``tools.hash_sign`` no existe
    aquí (divergencia 7); la caducidad la verifica el lector con ``max_age``.
    """
    payload = [company.pk, company._get_peppol_webhook_endpoint()]
    return signing.dumps(payload, salt=WEBHOOK_SIGNING_SALT)


def _get_user_from_token(cls, token, url):
    """≙ ``_get_user_from_token`` (``odoo19c: :593-611``).

    Devuelve el usuario de proxy que corresponde al token, o ``None``. Se
    conservan las tres guardas de la fuente: firma válida, la URL que llega
    empieza por el endpoint firmado, y el *fallback* heredado por id de
    usuario de proxy (que la fuente marca para retirar tras marzo de 2026,
    cuando caduquen los webhooks de 30 días).
    """
    try:
        payload = signing.loads(
            token,
            salt=WEBHOOK_SIGNING_SALT,
            max_age=timedelta(hours=WEBHOOK_TOKEN_EXPIRATION_HOURS),
        )
    except (signing.BadSignature, ValueError):
        return None

    identifier, endpoint = payload
    if not url.startswith(endpoint):
        return None

    company_model = AccountEdiProxyUser._meta.get_field('company_id').related_model
    company = company_model.objects.filter(pk=identifier).first()
    if company is not None and company.account_peppol_edi_user is not None:
        return company.account_peppol_edi_user
    return AccountEdiProxyUser.objects.filter(pk=identifier).first()


def _peppol_reset_webhook(self):
    """≙ ``_peppol_reset_webhook`` (``odoo19c: :613-616``)."""
    self._call_peppol_proxy(
        self._get_peppol_proxy_endpoint('2/set_webhook'),
        params={
            'webhook_url': self.company_id._get_peppol_webhook_endpoint(),
            'token': type(self)._generate_webhook_token(self.company_id),
        },
    )


def apply_account_peppol_account_edi_proxy_user_extensions():
    """Cuelga sobre ``account_edi_proxy_client.user`` el vocabulario Peppol —
    ≙ ``_inherit = 'account_edi_proxy_client.user'``. La llama
    ``AccountPeppolConfig.ready()``.

    ``_get_proxy_urls`` va con ``combine`` de fusión; el resto con el relevo
    por ``None`` que ``chain_method`` aplica por defecto.
    """
    _extend_selection_choices(
        AccountEdiProxyUser, 'proxy_type', [('peppol', 'PEPPOL')],
    )

    chain_method(
        AccountEdiProxyUser, '_get_proxy_urls',
        _get_proxy_urls, combine=_merge_with_previous,
    )
    chain_method(
        AccountEdiProxyUser, '_get_proxy_identification',
        classmethod(_get_proxy_identification),
    )

    for name, function in (
        ('_get_peppol_proxy_types', classmethod(_get_peppol_proxy_types)),
        ('_get_peppol_error_message', classmethod(_get_peppol_error_message)),
        ('_get_can_send_domain', classmethod(_get_can_send_domain)),
        ('_cron_peppol_get_new_documents', classmethod(_cron_peppol_get_new_documents)),
        ('_cron_peppol_get_message_status', classmethod(_cron_peppol_get_message_status)),
        ('_cron_peppol_get_participant_status', classmethod(_cron_peppol_get_participant_status)),
        ('_cron_peppol_webhook_keepalive', classmethod(_cron_peppol_webhook_keepalive)),
        ('_generate_webhook_token', classmethod(_generate_webhook_token)),
        ('_get_user_from_token', classmethod(_get_user_from_token)),
        ('_get_peppol_proxy_endpoint', _get_peppol_proxy_endpoint),
        ('_call_peppol_proxy', _call_peppol_proxy),
        ('_mark_connection_out_of_sync', _mark_connection_out_of_sync),
        ('_peppol_out_of_sync_reconnect_this_database',
         _peppol_out_of_sync_reconnect_this_database),
        ('_peppol_out_of_sync_disconnect_this_database',
         _peppol_out_of_sync_disconnect_this_database),
        ('_peppol_get_filetype', _peppol_get_filetype),
        ('_peppol_get_decoded_document', _peppol_get_decoded_document),
        ('_peppol_process_participant_status', _peppol_process_participant_status),
        ('_peppol_get_participant_status', _peppol_get_participant_status),
        ('_peppol_register_sender_as_receiver', _peppol_register_sender_as_receiver),
        ('_peppol_deregister_participant', _peppol_deregister_participant),
        ('_peppol_deregister_participant_to_sender', _peppol_deregister_participant_to_sender),
        ('_peppol_get_services', _peppol_get_services),
        ('_peppol_reset_webhook', _peppol_reset_webhook),
    ):
        chain_method(AccountEdiProxyUser, name, function)


__all__ = [
    'BATCH_SIZE',
    'apply_account_peppol_account_edi_proxy_user_extensions',
]
