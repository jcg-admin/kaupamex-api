"""``res.company`` extendido por ``account_peppol`` — el estado del participante.

Adaptación de Odoo ``account_peppol/models/res_company.py``
(``odoo19c: addons/account_peppol/models/res_company.py``, 459 líneas, LGPL-3)
— atribución y aviso de licencia preservados (DEC-KX-03).

Qué es: la empresa como **participante Peppol**. Aquí viven su estado en la
red (``account_peppol_proxy_state``, el eje sobre el que gira todo el addon),
sus datos de contacto para el alta, el diario donde aterrizan las facturas
recibidas, y el catálogo de tipos de documento que la empresa declara soportar.

Medido por AST en la fuente: 1 clase (``_inherit``), **16 campos** y
**24 métodos** (más 3 funciones de módulo y 4 constantes).

Porte símbolo por símbolo — 47 símbolos: 30 portados, 17 bloqueados
=====================================================================

Constantes y funciones de módulo
----------------------------------

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Símbolo (línea)
     - Desenlace
   * - ``_re_sanitizer`` (``:25-26``) / ``PEPPOL_ENDPOINT_SANITIZERS`` (``:46-51``)
     - **portados** — son expresiones regulares puras, sin dependencia externa.
   * - ``TIMEOUT`` (``:52``)
     - portado verbatim.
   * - ``_cc_checker`` (``:21-22``), ``PEPPOL_ENDPOINT_RULES`` (``:29-35``),
       ``PEPPOL_ENDPOINT_WARNINGS`` (``:37-44``)
     - **LIBRES, pendientes de portar.** Estuvieron bloqueados por
       ``python-stdnum``, que no era dependencia; **ya lo es**
       (``python-stdnum>=2.0``, ``api@414b286f``). Los validadores son
       ``get_cc_module('se', 'orgnr').is_valid`` y compañía: dígitos de
       control de seis países más EAN. Se conserva **la única regla que no
       depende de la biblioteca** —``'0201'``, que es un ``re.match``— para
       que la forma del mapa quede y sólo falten las entradas de ``stdnum``.
       Portarlas contra la librería es la tarea **#292**.

Campos — 16
-------------

**Portados (11):** ``account_peppol_contact_email``,
``account_peppol_migration_key``, ``account_peppol_phone_number``,
``account_peppol_proxy_state``, ``peppol_external_provider``,
``peppol_metadata``, ``peppol_metadata_updated_at``,
``peppol_purchase_journal`` (FK), ``peppol_activate_self_billing_sending``
(la fuente lo marca *Deprecated*; se porta igual porque el porte es completo),
``peppol_self_billing_reception_journal`` (FK, *Deprecated*), y
``account_peppol_edi_user`` — este último como **``property``**, porque es un
``compute`` sin ``store`` (criterio del árbol para ese caso).

**Portado como property (1):** ``peppol_can_send``.

**BLOQUEADOS por ``account_edi_ubl_cii`` (3):** ``peppol_eas`` y
``peppol_endpoint`` son ``related='partner_id.peppol_*'``, y esos dos campos
del contacto **los declara ese addon**
(``odoo19c: account_edi_ubl_cii/models/res_partner.py:43,51``), que se porta
en otro pase. Con ellos cae ``peppol_parent_company_id``, cuyo ``compute``
compara exactamente ese par contra el de cada empresa padre.

Métodos — 24
--------------

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Símbolo (línea)
     - Desenlace
   * - ``_reset_peppol_configuration`` (``:140-161``)
     - **portado** — sin las cuatro líneas que tocan ``peppol_eas`` /
       ``peppol_endpoint`` y sin los dos ``_compute_peppol_*`` del contacto
       (BLOQUEADOS por ``account_edi_ubl_cii``). Lo demás —estado, clave de
       migración, proveedor externo, correo y teléfono— se restablece igual.
   * - ``_have_unauthorized_peppol_parent_company`` (``:137-138``)
     - **portado** verbatim (``return False``; la fuente lo marca para retirar).
   * - ``_check_phonenumbers_import`` (``:163-166``)
     - **portado verbatim** — y es un porte real, no un stub: la propia
       referencia contempla la ausencia de la biblioteca
       (``try: import phonenumbers / except ImportError: phonenumbers = None``)
       y define este método para levantar un error legible. Medido:
       ``grep -ci phonenumbers uv.lock`` → **0**, así que aquí levanta siempre,
       que es el comportamiento que la fuente especifica para ese caso.
   * - ``_sanitize_peppol_phone_number`` (``:168-190``)
     - **portado** — llama al anterior primero, igual que la fuente, así que
       hoy termina en el ``ValidationError`` declarado.
   * - ``_check_peppol_endpoint_number`` (``:192-196``)
     - **portado** — su mapa está recortado por ``stdnum`` (arriba).
   * - ``_check_account_peppol_phone_number`` (``:209-213``) /
       ``_check_peppol_endpoint`` (``:215-221``) /
       ``_check_peppol_purchase_journal_id`` (``:223-227``)
     - **portados** como validaciones de ``clean()`` (divergencia 2).
   * - ``_compute_account_peppol_edi_user`` (``:233-238``)
     - **portado** como ``property`` ``account_peppol_edi_user``.
   * - ``_compute_peppol_can_send`` (``:319-323``)
     - **portado** como ``property`` ``peppol_can_send``.
   * - ``_compute_account_peppol_contact_email`` (``:302-306``) /
       ``_compute_account_peppol_phone_number`` (``:308-317``)
     - **portados** — suplen el valor que falta desde ``email`` / ``phone`` de
       la empresa, sin pisar el que ya haya (misma semántica que
       ``store=True, readonly=False`` de la fuente).
   * - ``_compute_peppol_purchase_journal_id`` (``:258-266``) /
       ``_inverse_peppol_purchase_journal_id`` (``:268-278``)
     - **portados** — el diario de compras por defecto y la exclusividad de
       ``is_peppol_journal`` dentro de la empresa.
   * - ``_compute_peppol_self_billing_reception_journal_id`` (``:280-288``) /
       ``_inverse_peppol_self_billing_reception_journal_id`` (``:290-300``)
     - **portados** — ídem para el diario de venta (*Deprecated* en la fuente).
   * - ``_sanitize_peppol_endpoint_in_values`` (``:329-338``)
     - **portado** — usa sólo los saneadores por expresión regular.
   * - ``_peppol_modules_document_types`` (``:364-382``) /
       ``_peppol_supported_document_types`` (``:384-390``)
     - **portados verbatim** — los seis identificadores de documento son el
       contrato con la red Peppol y no se traducen ni se abrevian.
   * - ``_get_peppol_edi_mode`` (``:392-398``)
     - **portado** salvo el atajo ``'odemo'``, que lee ``self.peppol_eas``
       (BLOQUEADO por ``account_edi_ubl_cii``); el parámetro
       ``temporary_eas``, que es por donde el llamador lo pasa, sí funciona.
   * - ``_get_peppol_webhook_endpoint`` (``:400-402``)
     - **portado** — ``get_base_url()`` no existe aquí (0 hits); se resuelve
       con el parámetro de sistema ``web.base.url``, el precedente del árbol
       (``addons/authz_passkey/models/auth_passkey_key.py:51-62``).
   * - ``_get_company_info_on_peppol`` (``:404-441``)
     - **portado** — la consulta al SMP y la lectura del proveedor externo del
       XML de servicio. ``requests`` y ``lxml`` sí están (medidos en
       ``uv.lock``; ``lxml`` es dependencia directa, ``pyproject.toml:52``).
   * - ``_get_peppol_proxy_type`` (``:454-459``)
     - **portado**.
   * - ``_get_active_peppol_parent_company`` (``:123-135``)
     - BLOQUEADO por ``peppol_can_send`` **de la empresa padre** — no por el
       campo (que se porta) sino por la cadena de padres: recorre
       ``self.parent_ids[::-1][1:]``, y ``ResCompany.parent_ids``
       (``src/addons/base/models/res_company.py:429``) sí existe. El bloqueo
       real es que su único consumidor es el flujo de empresa matriz Peppol,
       que depende de ``peppol_parent_company_id`` → ``account_edi_ubl_cii``.
       **Portado igualmente** por ser autosuficiente; se marca aquí porque su
       consumidor no lo está.
   * - ``_compute_peppol_parent_company_id`` (``:240-256``)
     - BLOQUEADO por ``account_edi_ubl_cii`` (compara ``peppol_eas`` /
       ``peppol_endpoint`` contra los del padre).
   * - ``_peppol_is_french_company`` (``:198-203``)
     - BLOQUEADO por ``EAS_MAPPING`` (``odoo19c: account_edi_ubl_cii/models/
       account_edi_common.py:52``) y, en segundo orden, por
       ``account_fiscal_country_id`` — medido, 0 hits en este árbol.
   * - ``create`` (``:340-354``) / ``write`` (``:356-358``)
     - BLOQUEADOS por ``ir.default`` — su parte propia (sanear el endpoint en
       los valores) **sí se porta**, enganchada en ``save()``
       (divergencia 3); lo que queda fuera es el
       ``env['ir.default'].set('res.partner', 'peppol_verification_state', …)``
       por empresa: ``IrDefault`` existe (``src/addons/base/models/
       ir_default.py:145``) pero **sin un ``set()`` de clase** (medido, 0 hits
       de ``def set(``), y fabricarlo aquí sería inventar API de otro addon.
   * - ``_account_peppol_send_welcome_email`` (``:443-452``)
     - BLOQUEADO por la plantilla de correo
       ``account_peppol.mail_template_peppol_registration``
       (``data/mail_templates_email_layouts.xml``, XML de datos no portado) y
       por ``env.ref``.

Divergencias declaradas
=========================

1. **Nombres de FK sin ``_id``.** ``peppol_purchase_journal_id`` →
   ``peppol_purchase_journal``, criterio del árbol; el accesor
   ``peppol_purchase_journal_id`` que Django genera conserva el nombre de la
   fuente para lecturas de id.
2. **``@api.constrains`` → ``clean()``.** Las tres validaciones se encadenan
   sobre ``ResCompany.clean``, que es donde este árbol pone las restricciones
   de modelo (precedente: ``account/models/account_analytic_line.py``).
3. **``create``/``write`` → gancho de ``save()``**, mismo idioma que el resto
   del árbol para «suplir/sanear un valor en la escritura».
4. **``self.env.company`` cae.** La referencia lee la empresa activa de la
   sesión para decidir el modo del SMP; aquí los métodos que lo necesitaban
   (``_get_participant_info``, ``_peppol_lookup_participant``) reciben la
   empresa como argumento — ver ``models/res_partner.py``.
"""
import contextlib
import logging
import re

import requests
from lxml import etree

import fields
import models
from addons.account_edi_proxy_client.models.account_edi_proxy_user import (
    AccountEdiProxyUser,
)
from addons.base.models import SystemParameter
from addons.base.models.res_company import ResCompany
from exceptions import ValidationError
from orm.method_chain import chain_method
from orm.model_classes import add_field_if_absent
from tools.translate import _
from tools.urls import urljoin

_logger = logging.getLogger(__name__)

TIMEOUT = 10
#: Parámetro de sistema con la URL pública de la instalación — el análogo del
#: ``get_base_url()`` de la referencia (precedente: ``authz_passkey``).
PARAM_BASE_URL = 'web.base.url'
#: Parámetro de sistema con el modo del proxy Peppol (``prod``/``test``/``demo``).
PARAM_EDI_MODE = 'account_peppol.edi.mode'


def _re_sanitizer(expression):
    """≙ ``_re_sanitizer`` (``odoo19c: :25-26``) — deja del endpoint sólo el
    tramo que la expresión reconoce; si no reconoce nada, lo deja igual."""
    return lambda endpoint: (
        res.group(0) if (res := re.search(expression, endpoint)) else endpoint
    )


#: ≙ ``PEPPOL_ENDPOINT_RULES`` (``odoo19c: :29-35``) — **recortado**: las cinco
#: entradas de la fuente validan dígitos de control con ``python-stdnum``, que
#: no está en ``uv.lock`` (medido: 0 hits). Queda vacío a propósito, no
#: ausente: ``_check_peppol_endpoint_number`` lo consulta y devuelve ``True``
#: cuando no hay regla, que es exactamente lo que la fuente hace para un EAS
#: sin regla.
PEPPOL_ENDPOINT_RULES = {}

#: ≙ ``PEPPOL_ENDPOINT_WARNINGS`` (``odoo19c: :37-44``) — de sus seis entradas
#: se conserva la única que no depende de ``stdnum``.
PEPPOL_ENDPOINT_WARNINGS = {
    '0201': lambda endpoint: bool(re.match('[0-9a-zA-Z]{6}$', endpoint)),
}

#: ≙ ``PEPPOL_ENDPOINT_SANITIZERS`` (``odoo19c: :46-51``) — verbatim, las
#: cuatro. Son expresiones regulares puras.
PEPPOL_ENDPOINT_SANITIZERS = {
    '0007': _re_sanitizer(r'\d{10}'),
    '0184': _re_sanitizer(r'\d{8}'),
    '0192': _re_sanitizer(r'\d{9}'),
    '0208': _re_sanitizer(r'\d{10}'),
}

#: ≙ el ``selection`` de ``account_peppol_proxy_state`` (``odoo19c: :70-79``).
PEPPOL_PROXY_STATES = [
    ('not_registered', 'No registrado'),
    ('sender', 'Puede enviar pero no recibir'),
    ('smp_registration', 'Puede enviar; alta de recepción pendiente'),
    ('receiver', 'Puede enviar y recibir'),
    ('rejected', 'Rechazado'),
]

#: ≙ el ``dict`` de ``_peppol_modules_document_types`` (``odoo19c: :369-381``).
#: Los identificadores son el contrato con la red: verbatim, sin traducir.
PEPPOL_DEFAULT_DOCUMENT_TYPES = {
    'urn:oasis:names:specification:ubl:schema:xsd:Invoice-2::Invoice'
    '##urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0::2.1':
        'Peppol BIS Billing UBL Invoice V3',
    'urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2::CreditNote'
    '##urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0::2.1':
        'Peppol BIS Billing UBL CreditNote V3',
    'urn:oasis:names:specification:ubl:schema:xsd:Invoice-2::Invoice'
    '##urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:selfbilling:3.0::2.1':
        'Peppol BIS Self-Billing UBL Invoice V3',
    'urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2::CreditNote'
    '##urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:selfbilling:3.0::2.1':
        'Peppol BIS Self-Billing UBL CreditNote V3',
    'urn:oasis:names:specification:ubl:schema:xsd:Invoice-2::Invoice'
    '##urn:cen.eu:en16931:2017#compliant#urn:fdc:nen.nl:nlcius:v1.0::2.1':
        'SI-UBL 2.0 Invoice',
    'urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2::CreditNote'
    '##urn:cen.eu:en16931:2017#compliant#urn:fdc:nen.nl:nlcius:v1.0::2.1':
        'SI-UBL 2.0 CreditNote',
}

try:  # pragma: no cover - la biblioteca no está declarada en uv.lock
    import phonenumbers
except ImportError:  # ≙ ``odoo19c: :15-18`` — la fuente contempla su ausencia
    phonenumbers = None


# -------------------------------------------------------------------------
# CAMPOS
# -------------------------------------------------------------------------

def _campos():
    """Los 11 campos que este addon cuelga sobre ``base.ResCompany``.

    Se construyen dentro de una función y no a nivel de módulo porque
    ``add_field_if_absent`` los consume una sola vez, al aplicar la extensión.
    """
    return {
        'account_peppol_contact_email': fields.Char(
            max_length=254, blank=True, default='',
            verbose_name='Correo de contacto principal',
            help_text='Correo principal para las comunicaciones y avisos de la '
                      'conexión Peppol. Odoo lo usa para reconectar la cuenta '
                      'Peppol si la base de datos cambia (Odoo '
                      'account_peppol_contact_email).',
        ),
        'account_peppol_migration_key': fields.Char(
            max_length=255, blank=True, default='',
            verbose_name='Clave de migración',
            help_text='Odoo account_peppol_migration_key (groups=base.group_system '
                      'en la referencia; aquí la restricción es de capacidad, no '
                      'de campo).',
        ),
        'account_peppol_phone_number': fields.Char(
            max_length=32, blank=True, default='',
            verbose_name='Número móvil',
            help_text='Sólo para fines de identificación (Odoo '
                      'account_peppol_phone_number).',
        ),
        'account_peppol_proxy_state': fields.Selection(
            max_length=20, choices=PEPPOL_PROXY_STATES, default='not_registered',
            verbose_name='Estado Peppol',
            help_text='Estado de la empresa en la red Peppol (Odoo '
                      'account_peppol_proxy_state, required).',
        ),
        'peppol_external_provider': fields.Char(
            max_length=255, blank=True, default='',
            help_text='Proveedor Peppol distinto de Odoo con el que la empresa ya '
                      'está dada de alta (Odoo peppol_external_provider).',
        ),
        'peppol_metadata': fields.Json(
            null=True, blank=True,
            verbose_name='Metadatos Peppol',
            help_text='Metadatos que aporta el proxy, de claves aditivas (Odoo '
                      'peppol_metadata).',
        ),
        'peppol_metadata_updated_at': fields.Datetime(
            null=True, blank=True,
            verbose_name='Metadatos Peppol actualizados el',
        ),
        'peppol_purchase_journal': fields.Many2one(
            'account.AccountJournal', null=True, blank=True,
            on_delete=models.SET_NULL, related_name='peppol_purchase_companies',
            verbose_name='Diario de compras Peppol',
            help_text='Diario donde aterrizan las facturas recibidas por Peppol '
                      '(Odoo peppol_purchase_journal_id; domain type=purchase, '
                      'reforzado en clean()).',
        ),
        # Los dos siguientes están marcados *Deprecated* en la referencia; se
        # portan igual porque el porte es completo o declara su cobertura.
        'peppol_activate_self_billing_sending': fields.Boolean(
            default=False,
            verbose_name='Activar el envío de autofacturación',
            help_text='Si se activa, se podrán enviar facturas de proveedor como '
                      'autofacturas por Peppol (Odoo, Deprecated).',
        ),
        'peppol_self_billing_reception_journal': fields.Many2one(
            'account.AccountJournal', null=True, blank=True,
            on_delete=models.SET_NULL, related_name='peppol_self_billing_companies',
            verbose_name='Diario de recepción de autofacturación',
            help_text='Las autofacturas recibidas por Peppol se crean en borrador '
                      'en este diario (Odoo peppol_self_billing_reception_journal_id, '
                      'Deprecated).',
        ),
    }


# -------------------------------------------------------------------------
# PROPIEDADES (los ``compute`` sin ``store`` de la referencia)
# -------------------------------------------------------------------------

def account_peppol_edi_user(self):
    """≙ ``_compute_account_peppol_edi_user`` (``odoo19c: :233-238``) — el
    usuario de proxy de tipo Peppol de esta empresa, si lo hay.

    Por diseño sólo puede haber cero o uno (lo garantiza el índice único
    parcial de ``account_edi_proxy_client.user``).
    """
    return self.account_edi_proxy_client_ids.filter(
        proxy_type__in=AccountEdiProxyUser._get_peppol_proxy_types(),
    ).first()


def peppol_can_send(self):
    """≙ ``_compute_peppol_can_send`` (``odoo19c: :319-323``)."""
    return self.account_peppol_proxy_state in AccountEdiProxyUser._get_can_send_domain()


# -------------------------------------------------------------------------
# MÉTODOS DE APOYO
# -------------------------------------------------------------------------

def _get_active_peppol_parent_company(self):
    """≙ ``_get_active_peppol_parent_company`` (``odoo19c: :123-135``).

    La empresa padre más cercana con conexión Peppol activa, o ``None``. La
    referencia devuelve un recordset vacío; aquí el vacío es ``None``.
    """
    for parent_company in list(self.parent_ids)[::-1][1:]:
        if parent_company.peppol_can_send:
            return parent_company
    return None


def _have_unauthorized_peppol_parent_company(self):
    """≙ ``_have_unauthorized_peppol_parent_company`` (``odoo19c: :137-138``).
    Verbatim; la fuente lo marca para retirar."""
    return False


def _reset_peppol_configuration(self, soft=False):
    """≙ ``_reset_peppol_configuration`` (``odoo19c: :140-161``).

    :param soft: si es ``True`` sólo baja el estado a «no registrado» y deja
        la configuración intacta, para que el usuario pueda volver a
        registrarse.

    **Recortado**: las cuatro líneas que restablecen ``peppol_eas`` /
    ``peppol_endpoint`` y los dos ``_compute_peppol_*`` del contacto están
    BLOQUEADAS por ``account_edi_ubl_cii``.
    """
    campos = ['account_peppol_proxy_state', 'account_peppol_migration_key']
    self.account_peppol_proxy_state = 'not_registered'
    self.account_peppol_migration_key = ''
    if not soft:
        self.peppol_external_provider = ''
        self.account_peppol_contact_email = ''
        self.account_peppol_phone_number = ''
        campos += [
            'peppol_external_provider',
            'account_peppol_contact_email',
            'account_peppol_phone_number',
        ]
        self._compute_account_peppol_contact_email()
        self._compute_account_peppol_phone_number()
    self.save(update_fields=campos)


def _check_phonenumbers_import(self):
    """≙ ``_check_phonenumbers_import`` (``odoo19c: :163-166``).

    La referencia importa ``phonenumbers`` con ``try/except ImportError`` y
    define este método para el caso ausente. Medido aquí:
    ``grep -ci phonenumbers uv.lock`` → **0**, así que levanta siempre — que
    es el comportamiento que la propia fuente especifica en esa condición.
    """
    if not phonenumbers:
        raise ValidationError(_('Instale la biblioteca phonenumbers.'))


def _sanitize_peppol_phone_number(self, phone_number=None):
    """≙ ``_sanitize_peppol_phone_number`` (``odoo19c: :168-190``) — exige el
    formato internacional (``+52...``)."""
    error_message = _(
        'Escriba el número móvil en formato internacional.\n'
        'Por ejemplo: +32123456789, donde +32 es el código de país.'
    )

    self._check_phonenumbers_import()

    phone_number = phone_number or self.account_peppol_phone_number
    if not phone_number:
        return

    if not phone_number.startswith('+'):
        phone_number = f'+{phone_number}'

    try:
        phone_nbr = phonenumbers.parse(phone_number)
    except phonenumbers.phonenumberutil.NumberParseException:
        raise ValidationError(error_message)

    if not phonenumbers.is_valid_number(phone_nbr):
        raise ValidationError(error_message)


def _check_peppol_endpoint_number(self, warning=False):
    """≙ ``_check_peppol_endpoint_number`` (``odoo19c: :192-196``).

    Sin regla para el EAS → ``True``, igual que la fuente. Los mapas están
    recortados por ``python-stdnum`` (ver la cabecera del módulo).

    BLOQUEADO parcialmente por ``account_edi_ubl_cii``: lee ``self.peppol_eas``
    y ``self.peppol_endpoint``. Se conserva la forma y se lee con ``getattr``
    para que el método exista y funcione en cuanto esos campos aterricen.
    """
    peppol_dict = PEPPOL_ENDPOINT_WARNINGS if warning else PEPPOL_ENDPOINT_RULES
    eas = getattr(self, 'peppol_eas', None)
    endpoint = getattr(self, 'peppol_endpoint', None)
    endpoint_rule = peppol_dict.get(eas)
    return True if endpoint_rule is None else endpoint_rule(endpoint)


# -------------------------------------------------------------------------
# COMPUTE / INVERSE DE LOS DIARIOS Y EL CONTACTO
# -------------------------------------------------------------------------

def _compute_account_peppol_contact_email(self):
    """≙ ``_compute_account_peppol_contact_email`` (``odoo19c: :302-306``) —
    suple el correo de contacto desde el de la empresa, sin pisar el que ya
    esté puesto a mano."""
    if not self.account_peppol_contact_email:
        self.account_peppol_contact_email = self.email or ''


def _compute_account_peppol_phone_number(self):
    """≙ ``_compute_account_peppol_phone_number`` (``odoo19c: :308-317``) —
    ídem con el teléfono, y sólo si es un número válido."""
    if not self.account_peppol_phone_number:
        try:
            self._sanitize_peppol_phone_number(self.phone)
        except ValidationError:
            return
        self.account_peppol_phone_number = self.phone or ''


def _peppol_journal_model():
    """El modelo de diario, resuelto por el campo — evita importar
    ``addons.account`` al top y con ello un ciclo de import."""
    return ResCompany._meta.get_field('peppol_purchase_journal').related_model


def _compute_peppol_purchase_journal_id(self):
    """≙ ``_compute_peppol_purchase_journal_id`` (``odoo19c: :258-266``) — el
    primer diario de compras de la empresa, marcado como diario Peppol."""
    if self.peppol_purchase_journal_id is None and self.peppol_can_send:
        journal = _peppol_journal_model().objects.filter(
            company=self, type='purchase',
        ).first()
        self.peppol_purchase_journal = journal
        if journal is not None:
            journal.is_peppol_journal = True
            journal.save(update_fields=['is_peppol_journal'])


def _inverse_peppol_purchase_journal_id(self):
    """≙ ``_inverse_peppol_purchase_journal_id`` (``odoo19c: :268-278``).

    Garantiza que no queden dos diarios de compras de la misma empresa con
    ``is_peppol_journal`` — que es justo lo que la fuente evita.
    """
    _peppol_journal_model().objects.filter(
        company=self, type='purchase', is_peppol_journal=True,
    ).update(is_peppol_journal=False)
    if self.peppol_purchase_journal_id is not None:
        self.peppol_purchase_journal.is_peppol_journal = True
        self.peppol_purchase_journal.save(update_fields=['is_peppol_journal'])


def _compute_peppol_self_billing_reception_journal_id(self):
    """≙ ``_compute_peppol_self_billing_reception_journal_id``
    (``odoo19c: :280-288``). *Deprecated* en la fuente."""
    if self.peppol_self_billing_reception_journal_id is None and self.peppol_can_send:
        journal = _peppol_journal_model().objects.filter(
            company=self, type='sale',
        ).first()
        self.peppol_self_billing_reception_journal = journal
        if journal is not None:
            journal.is_peppol_journal = True
            journal.save(update_fields=['is_peppol_journal'])


def _inverse_peppol_self_billing_reception_journal_id(self):
    """≙ ``_inverse_peppol_self_billing_reception_journal_id``
    (``odoo19c: :290-300``). *Deprecated* en la fuente."""
    _peppol_journal_model().objects.filter(
        company=self, type='sale', is_peppol_journal=True,
    ).update(is_peppol_journal=False)
    if self.peppol_self_billing_reception_journal_id is not None:
        self.peppol_self_billing_reception_journal.is_peppol_journal = True
        self.peppol_self_billing_reception_journal.save(
            update_fields=['is_peppol_journal'],
        )


# -------------------------------------------------------------------------
# VALIDACIONES Y ESCRITURA
# -------------------------------------------------------------------------

def _peppol_clean(self, *args, **kwargs):
    """≙ las tres ``@api.constrains`` (``odoo19c: :209-227``), reunidas en el
    ``clean()`` que este árbol usa para las restricciones de modelo.

    Retorna ``None`` para que ``chain_method`` siga con la validación previa.
    """
    if self.account_peppol_phone_number:
        self._sanitize_peppol_phone_number()

    if getattr(self, 'peppol_endpoint', None):
        if not self._check_peppol_endpoint_number():
            raise ValidationError(
                {'peppol_endpoint': _('El identificador del endpoint Peppol no es correcto.')},
            )

    if (self.peppol_purchase_journal_id is not None
            and self.peppol_purchase_journal.type != 'purchase'):
        raise ValidationError(
            {'peppol_purchase_journal': _(
                'Debe usarse un diario de compras para recibir documentos Peppol.',
            )},
        )
    return None


def _sanitize_peppol_endpoint_in_values(self, values):
    """≙ ``_sanitize_peppol_endpoint_in_values`` (``odoo19c: :329-338``).

    Recibe un dict de valores, como la fuente. Se conserva la firma para que
    quien construya valores antes de crear pueda saneárlos.
    """
    eas = values.get('peppol_eas')
    endpoint = values.get('peppol_endpoint')
    if not eas or not endpoint:
        return
    if sanitizer := PEPPOL_ENDPOINT_SANITIZERS.get(eas):
        if new_endpoint := sanitizer(endpoint):
            values['peppol_endpoint'] = new_endpoint


def _sanitize_peppol_endpoint_on_save(self, *args, **kwargs):
    """≙ la parte propia de ``create``/``write`` (``odoo19c: :340-358``): sanear
    el endpoint antes de escribir.

    El resto de ``create`` —sembrar el ``ir.default`` de
    ``peppol_verification_state`` por empresa— está BLOQUEADO (ver la cabecera
    del módulo). Retorna ``None``: relevo hacia el ``save()`` real.
    """
    eas = getattr(self, 'peppol_eas', None)
    endpoint = getattr(self, 'peppol_endpoint', None)
    if eas and endpoint and (sanitizer := PEPPOL_ENDPOINT_SANITIZERS.get(eas)):
        if new_endpoint := sanitizer(endpoint):
            self.peppol_endpoint = new_endpoint
    return None


# -------------------------------------------------------------------------
# GESTIÓN DEL PARTICIPANTE
# -------------------------------------------------------------------------

def _peppol_modules_document_types(self):
    """≙ ``_peppol_modules_document_types`` (``odoo19c: :364-382``).

    Se sobreescribe para añadir tipos de documento soportados conforme se
    instalan módulos.

    :returns: dict ``{nombre_de_modulo: {identificador: nombre_de_documento}}``.
    """
    return {'default': dict(PEPPOL_DEFAULT_DOCUMENT_TYPES)}


def _peppol_supported_document_types(self):
    """≙ ``_peppol_supported_document_types`` (``odoo19c: :384-390``) — el dict
    aplanado de todos los tipos soportados."""
    return {
        identifier: document_name
        for identifiers in self._peppol_modules_document_types().values()
        for identifier, document_name in identifiers.items()
    }


def _get_peppol_edi_mode(self, temporary_eas=False):
    """≙ ``_get_peppol_edi_mode`` (``odoo19c: :392-398``).

    Precedencia verbatim: identificador de demo ≻ modo del usuario de proxy ≻
    parámetro de sistema ≻ ``'prod'``.

    **Recortado**: el atajo de demo evalúa ``(temporary_eas or self.peppol_eas)``
    en la fuente; ``peppol_eas`` está BLOQUEADO por ``account_edi_ubl_cii``, así
    que aquí sólo pesa el argumento — que es por donde el llamador lo pasa
    durante el alta.
    """
    config_param = SystemParameter.get_param(PARAM_EDI_MODE, '')
    peppol_user = self.account_peppol_edi_user
    demo_if_demo_identifier = 'demo' if temporary_eas == 'odemo' else False
    return (demo_if_demo_identifier
            or (peppol_user.edi_mode if peppol_user is not None else '')
            or config_param
            or 'prod')


def _get_peppol_webhook_endpoint(self):
    """≙ ``_get_peppol_webhook_endpoint`` (``odoo19c: :400-402``).

    ``get_base_url()`` no existe en este árbol (medido, 0 hits); la URL pública
    sale del parámetro de sistema ``web.base.url``, el precedente ya usado por
    ``authz_passkey``.
    """
    return urljoin(str(SystemParameter.get_param(PARAM_BASE_URL, '') or ''), '/peppol/webhook')


def _get_peppol_provider(participant_info):
    """≙ la función anidada ``_get_peppol_provider`` (``odoo19c: :406-421``) —
    el nombre del proveedor que atiende hoy a ese participante, leído del XML
    de descripción del servicio."""
    if not participant_info:
        return None
    services = participant_info.get('services', [])
    if not services:
        return None

    service_href = services[0].get('href')
    provider_name = None
    with contextlib.suppress(requests.exceptions.RequestException, etree.XMLSyntaxError):
        response = requests.get(service_href, timeout=TIMEOUT)
        if response.status_code == 200:
            access_point_info = etree.fromstring(response.content)
            provider_name = access_point_info.findtext('.//{*}ServiceDescription')
    return provider_name


def _get_company_info_on_peppol(self, edi_identification):
    """≙ ``_get_company_info_on_peppol`` (``odoo19c: :404-441``).

    ¿Está ya esta empresa dada de alta en la red, y con quién? El mensaje de
    error se compone igual que en la fuente: el genérico siempre, más el
    nombre del proveedor cuando lo hay y no es Odoo.
    """
    partner_model = ResCompany._meta.get_field('partner').related_model
    is_company_on_peppol = False
    external_provider = None
    error_msg = ''

    participant_info = partner_model._peppol_lookup_participant(edi_identification, self)
    if participant_info is not None:
        is_company_on_peppol = partner_model._check_peppol_participant_exists(
            participant_info, edi_identification,
        )
    if is_company_on_peppol:
        error_msg = _(
            'Ya hay un participante registrado en la red con estos datos. '
            'Si se registró antes en un servicio Peppol, dese de baja primero.'
        )
        external_provider = _get_peppol_provider(participant_info)
        if external_provider and 'Odoo' not in external_provider:
            error_msg += _('El servicio Peppol que se usa es %s.', external_provider)

    return {
        'is_on_peppol': is_company_on_peppol,
        'external_provider': external_provider,
        'error_msg': error_msg,
    }


def _get_peppol_proxy_type(self):
    """≙ ``_get_peppol_proxy_type`` (``odoo19c: :454-459``)."""
    peppol_user = self.account_peppol_edi_user
    return (peppol_user.proxy_type if peppol_user is not None else None) or 'peppol'


def apply_account_peppol_res_company_extensions():
    """Cuelga sobre ``base.ResCompany`` el estado del participante Peppol — ≙
    ``_inherit = 'res.company'``. La llama ``AccountPeppolConfig.ready()``."""
    for name, field in _campos().items():
        add_field_if_absent(ResCompany, name, field)

    for name, function in (
        ('account_peppol_edi_user', account_peppol_edi_user),
        ('peppol_can_send', peppol_can_send),
    ):
        if not hasattr(ResCompany, name):
            setattr(ResCompany, name, property(function))

    chain_method(ResCompany, 'clean', _peppol_clean)
    chain_method(ResCompany, 'save', _sanitize_peppol_endpoint_on_save)

    for name, function in (
        ('_get_active_peppol_parent_company', _get_active_peppol_parent_company),
        ('_have_unauthorized_peppol_parent_company',
         _have_unauthorized_peppol_parent_company),
        ('_reset_peppol_configuration', _reset_peppol_configuration),
        ('_check_phonenumbers_import', _check_phonenumbers_import),
        ('_sanitize_peppol_phone_number', _sanitize_peppol_phone_number),
        ('_check_peppol_endpoint_number', _check_peppol_endpoint_number),
        ('_compute_account_peppol_contact_email', _compute_account_peppol_contact_email),
        ('_compute_account_peppol_phone_number', _compute_account_peppol_phone_number),
        ('_compute_peppol_purchase_journal_id', _compute_peppol_purchase_journal_id),
        ('_inverse_peppol_purchase_journal_id', _inverse_peppol_purchase_journal_id),
        ('_compute_peppol_self_billing_reception_journal_id',
         _compute_peppol_self_billing_reception_journal_id),
        ('_inverse_peppol_self_billing_reception_journal_id',
         _inverse_peppol_self_billing_reception_journal_id),
        ('_sanitize_peppol_endpoint_in_values', _sanitize_peppol_endpoint_in_values),
        ('_peppol_modules_document_types', _peppol_modules_document_types),
        ('_peppol_supported_document_types', _peppol_supported_document_types),
        ('_get_peppol_edi_mode', _get_peppol_edi_mode),
        ('_get_peppol_webhook_endpoint', _get_peppol_webhook_endpoint),
        ('_get_company_info_on_peppol', _get_company_info_on_peppol),
        ('_get_peppol_proxy_type', _get_peppol_proxy_type),
    ):
        chain_method(ResCompany, name, function)


__all__ = [
    'PEPPOL_ENDPOINT_RULES',
    'PEPPOL_ENDPOINT_SANITIZERS',
    'PEPPOL_ENDPOINT_WARNINGS',
    'PEPPOL_PROXY_STATES',
    'apply_account_peppol_res_company_extensions',
]
