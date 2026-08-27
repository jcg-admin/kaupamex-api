r"""``res.partner`` — lo que ``account_edi_ubl_cii`` le cuelga (≙ ``_inherit``).

Adaptación de ``odoo19c: addons/account_edi_ubl_cii/models/res_partner.py``
(``odoo-tools@622ddc2a``, LGPL-3, 349 líneas) — atribución y aviso de licencia
preservados (DEC-KX-03).

Cobertura: 20 de 20 símbolos presentes — **12 portados, 8 bloqueados**
=======================================================================

(20 = 1 función de módulo + 19 métodos. Los 8 bloqueados llaman a
:func:`_blocked`; ``_build_error_peppol_endpoint`` cuenta como **portado** —
sólo su rama ``eas == '0009'`` levanta, ver su fila.)

.. list-table::
   :header-rows: 1
   :widths: 44 12 44

   * - Símbolo
     - Estado
     - Nota
   * - ``sanitize_peppol_endpoint`` (módulo)
     - portado
     - regex pura, verbatim
   * - ``_get_ubl_cii_formats``
     - portado
     -
   * - ``_get_ubl_cii_formats_info``
     - portado
     - trae ``PEPPOL_DEFAULT_COUNTRIES`` vendorizado (ver abajo)
   * - ``_get_ubl_cii_formats_by_country``
     - portado
     -
   * - ``_get_peppol_formats``
     - portado
     -
   * - ``_peppol_eas_endpoint_depends``
     - portado
     - devuelve los nombres de la referencia; es la lista que las
       localizaciones extienden
   * - ``_compute_is_ubl_format`` / ``_compute_is_peppol_edi_format``
     - portados
     - como ``property`` (compute sin ``store``), ver "Campos" abajo
   * - ``_build_error_peppol_endpoint``
     - portado
     - **con una rama bloqueada**: ``eas == '0009'`` valida SIRET con
       ``stdnum.fr.siret.is_valid`` (0 hits en ``uv.lock``) — dígito de
       control, no se transcribe a mano. Las otras cuatro reglas
       (``0208``, ``0007``, ``EM``, caracteres/longitud) sí se portan
   * - ``_check_peppol_fields``
     - portado
     - la restricción se instala; su **disparo** por el ORM al escribir es la
       divergencia declarada abajo
   * - ``_get_edi_builder``
     - portado
     - **divergencia**: ``env['account.edi.xml.ubl_de']`` → la clase Python
       directa. Los constructores de esta familia son clases planas (no
       modelos Django), así que ``orm.registry.model_by_name`` no los ve; el
       mapa por clave se conserva idéntico
   * - ``_import_retrieve_customer_from_eas_endpoint``
     - portado
     - devuelve un plan de búsqueda (``dict``), sin tocar el ORM
   * - ``_get_suggested_ubl_cii_edi_format``
     - bloqueado
     - ``ResPartner.commercial_partner_id`` y ``_deduce_country_code()``:
       **0 hits** en el árbol
   * - ``_get_ubl_cii_edi_format`` · ``_get_suggested_peppol_edi_format`` ·
       ``_get_peppol_edi_format``
     - bloqueados
     - ídem (los tres orquestan el anterior o ``ensure_one()``, que tampoco
       existe: 0 hits)
   * - ``_get_peppol_endpoint_value``
     - bloqueado
     - recorre ``self._fields`` (introspección del ORM de la referencia)
   * - ``_compute_peppol_endpoint`` · ``_compute_peppol_eas``
     - bloqueados
     - ``_deduce_country_code()`` (0 hits) y ``_get_peppol_endpoint_value``
   * - ``_compute_available_peppol_eas``
     - bloqueado
     - lee ``self._fields['peppol_eas'].selection`` — introspección del ORM de
       la referencia. La lista sí está publicada aquí como
       :data:`PEPPOL_EAS_CHOICES`, así que el desbloqueo es de una línea

Campos — 7 de la referencia, 6 declarados aquí y 1 con divergencia
====================================================================

Se cuelgan sobre ``base.ResPartner`` con ``add_field_if_absent``, el mismo
mecanismo y el mismo sitio que ``account_peppol/models/res_partner.py`` usa
para ``peppol_verification_state`` (que **no** declara los de aquí: su propio
docstring los atribuye explícitamente a este addon — sin colisión, medido).

* ``peppol_endpoint`` (``Char``) y ``peppol_eas`` (``Selection``, 90 valores)
  son **columnas reales**: la referencia las declara ``store=True,
  readonly=False``, es decir computadas con valor persistido y editable a
  mano. Aquí se persisten y su ``compute`` está bloqueado (arriba), que es
  exactamente la mitad que falta.
* ``is_ubl_format``, ``is_peppol_edi_format`` y ``available_peppol_eas`` son
  ``compute`` **sin** ``store`` en la referencia → ``property`` (vía
  ``extend_model(propiedades=…)``), no columna.
* ``invoice_edi_format`` — **divergencia declarada**. La referencia hace
  ``selection_add=[…]`` sobre un campo que declara ``account``. En este árbol
  ``account/models/partner.py:235`` declara ``invoice_edi_format_store``
  (``Char``) y **no** el ``invoice_edi_format`` computado (medido: 0 hits del
  símbolo). No se inventa aquí un campo que pertenece a ``account``: las siete
  claves que este addon aporta se publican como
  :data:`UBL_CII_INVOICE_EDI_FORMATS` y los métodos leen
  ``invoice_edi_format_store``, que es donde la referencia persiste el mismo
  valor. Sucesor: portar el ``invoice_edi_format`` computado en ``account``.

``@api.constrains`` — qué se porta y qué no
=============================================

``_check_peppol_fields`` se instala con ``chain_method`` y **se puede invocar**;
lo que no se porta es su **disparo automático** al escribir, porque en la
referencia lo dispara el ORM y aquí lo dispararía ``Model.full_clean()``, que
Django no llama en ``save()``. Es la misma divergencia que
``account/models/account_cash_rounding.py`` ya declaró para su propia
``@api.constrains``.

Sustituciones medidas
======================

* ``stdnum.fr.siret`` — **0 hits en ``uv.lock``**; sólo lo usa la rama
  ``0009`` de ``_build_error_peppol_endpoint`` (ver arriba).
* ``PEPPOL_DEFAULT_COUNTRIES`` — la referencia la importa de
  ``account/models/company.py:34-38``; ese archivo está portado pero **no**
  trae la constante (0 hits). Se vendoriza aquí verbatim, con su hogar
  correcto declarado (``account``), fuera del write-set de este pase.
* ``single_email_re`` — sí existe (``src/tools/mail.py:28``) y se usa tal cual.
* ``EAS_MAPPING`` — la fuente la importa para ``_compute_peppol_endpoint`` y
  ``_compute_peppol_eas``, los dos bloqueados; no se importa aquí para no dejar
  un import sin consumidor vivo. Sigue declarada en ``account_edi_common.py``.
"""
import re

import fields
from exceptions import UserError
from orm.method_chain import chain_method
from orm.model_classes import add_field_if_absent
from tools.mail import single_email_re
from tools.translate import _

from addons.base.models.res_partner import ResPartner

from .account_edi_common import _blocked
from .account_edi_xml_cii_facturx import AccountEdiXmlCii
from .account_edi_xml_ubl_a_nz import AccountEdiXmlUbl_A_Nz
from .account_edi_xml_ubl_bis3 import AccountEdiXmlUBLBIS3
from .account_edi_xml_ubl_nlcius import AccountEdiXmlUbl_Nl
from .account_edi_xml_ubl_sg import AccountEdiXmlUbl_Sg
from .account_edi_xml_ubl_xrechnung import AccountEdiXmlUbl_De

#: ≙ ``odoo19c: addons/account/models/company.py:34-38`` — vendorizada; su
#: hogar correcto es ``addons/account``, fuera del write-set de este pase.
PEPPOL_DEFAULT_COUNTRIES = [
    'AT', 'BE', 'CH', 'CY', 'CZ', 'DE', 'DK', 'EE', 'ES', 'FI',
    'FR', 'IE', 'IS', 'LT', 'LU', 'LV', 'MT', 'NL', 'NO', 'SE',
    'SI',
]

#: Las siete claves que este addon aporta al ``invoice_edi_format`` de la
#: referencia (``selection_add``, ``odoo19c: :30-40``). Ver "Campos" en el
#: docstring del módulo para por qué no se declara el campo aquí.
UBL_CII_INVOICE_EDI_FORMATS = [
    ('facturx', "France (FacturX)"),
    ('ubl_bis3', "EU Standard (Peppol Bis 3.0)"),
    ('zugferd', "Germany (ZUGFeRD)"),
    ('xrechnung', "Germany (XRechnung)"),
    ('nlcius', "Netherlands (NLCIUS)"),
    ('ubl_a_nz', "Australia (BIS Billing 3.0 A-NZ)"),
    ('ubl_sg', "Singapore (BIS Billing 3.0 SG)"),
]

PEPPOL_ENDPOINT_INVALIDCHARS_RE = re.compile(r'[^a-zA-Z\d\-._~]')
PEPPOL_ENDPOINT_INVALID_CHARS_RE_BY_EAS = {
    '0208': re.compile(r'[^0-9]'),
    '9925': re.compile(r'[^beBE0-9]'),
    'EM': re.compile(r'[^a-zA-Z\d\-._@]'),
}

#: ≙ el ``selection`` de ``peppol_eas`` (``odoo19c: :51-149``), verbatim.
PEPPOL_EAS_CHOICES = [
    ('9923', "Albania VAT"),
    ('9922', "Andorra VAT"),
    ('0151', "Australia ABN"),
    ('9914', "Austria UID"),
    ('9915', "Austria VOKZ"),
    ('0208', "Belgian Company Registry"),
    ('9925', "Belgian VAT"),
    ('9924', "Bosnia and Herzegovina VAT"),
    ('9926', "Bulgaria VAT"),
    ('9934', "Croatia VAT"),
    ('9928', "Cyprus VAT"),
    ('9929', "Czech Republic VAT"),
    ('0096', "Denmark P"),
    ('0184', "Denmark CVR"),
    ('0198', "Denmark SE"),
    ('0191', "Estonia Company code"),
    ('9931', "Estonia VAT"),
    ('0037', "Finland LY-tunnus"),
    ('0216', "Finland OVT code"),
    ('0213', "Finland VAT"),
    ('0002', "France SIRENE"),
    ('0009', "France SIRET"),
    ('9957', "France VAT"),
    ('0225', "France FRCTC Electronic Address"),
    ('0240', "France Register of legal persons"),
    ('0246', "German Electronic Business Address"),
    ('0204', "Germany Leitweg-ID"),
    ('9930', "Germany VAT"),
    ('9933', "Greece VAT"),
    ('9910', "Hungary VAT"),
    ('0196', "Iceland Kennitala"),
    ('9935', "Ireland VAT"),
    ('0211', "Italia Partita IVA"),
    ('0097', "Italia FTI"),
    ('0188', "Japan SST"),
    ('0221', "Japan IIN"),
    ('0218', "Latvia Unified registration number"),
    ('9939', "Latvia VAT"),
    ('9936', "Liechtenstein VAT"),
    ('0200', "Lithuania JAK"),
    ('9937', "Lithuania VAT"),
    ('9938', "Luxembourg VAT"),
    ('9942', "Macedonia VAT"),
    ('0230', "Malaysia"),
    ('9943', "Malta VAT"),
    ('9940', "Monaco VAT"),
    ('9941', "Montenegro VAT"),
    ('0106', "Netherlands KvK"),
    ('0190', "Netherlands OIN"),
    ('9944', "Netherlands VAT"),
    ('0244', "Nigeria Tax Identification"),
    ('0192', "Norway Org.nr."),
    ('9945', "Poland VAT"),
    ('9946', "Portugal VAT"),
    ('9947', "Romania VAT"),
    ('9948', "Serbia VAT"),
    ('0195', "Singapore UEN"),
    ('0245', "SK Tax identification number (DIČ)"),
    ('9949', "Slovenia VAT"),
    ('9950', "Slovakia VAT"),
    ('9920', "Spain VAT"),
    ('0007', "Sweden Org.nr."),
    ('9955', "Sweden VAT"),
    ('9927', "Swiss VAT"),
    ('0183', "Swiss UIDB"),
    ('9952', "Turkey VAT"),
    ('0235', "UAE Tax Identification Number (TIN)"),
    ('9932', "United Kingdom VAT"),
    ('9959', "USA EIN"),
    ('0060', "DUNS Number"),
    ('0088', "EAN Location Code"),
    ('0130', "Directorates of the European Commission"),
    ('0135', "SIA Object Identifiers"),
    ('0142', "SECETI Object Identifiers"),
    ('0193', "UBL.BE party identifier"),
    ('0199', "Legal Entity Identifier (LEI)"),
    ('0201', "Codice Univoco Unità Organizzativa iPA"),
    ('0202', "Indirizzo di Posta Elettronica Certificata"),
    ('0209', "GS1 identification keys"),
    ('0210', "Codice Fiscale"),
    ('9913', "Business Registers Network"),
    ('9918', "S.W.I.F.T"),
    ('9919', "Kennziffer des Unternehmensregisters"),
    ('9951', "San Marino VAT"),
    ('9953', "Vatican VAT"),
    ('AN', "O.F.T.P. (ODETTE File Transfer Protocol)"),
    ('AQ', "X.400 address for mail text"),
    ('AS', "AS2 exchange"),
    ('AU', "File Transfer Protocol"),
    ('EM', "Electronic mail"),
]


def sanitize_peppol_endpoint(peppol_endpoint, eas=None):
    """≙ ``sanitize_peppol_endpoint`` (``odoo19c: :20-24``) — verbatim."""
    if not peppol_endpoint:
        return peppol_endpoint
    sanitizer = PEPPOL_ENDPOINT_INVALID_CHARS_RE_BY_EAS.get(
        eas, PEPPOL_ENDPOINT_INVALIDCHARS_RE)
    return sanitizer.sub('', peppol_endpoint)


def _extra_fields():
    """Los dos campos con columna real que este addon cuelga sobre ``res.partner``.

    ``is_ubl_format``, ``is_peppol_edi_format`` y ``available_peppol_eas`` NO
    están aquí: son ``compute`` sin ``store`` en la referencia y se instalan
    como ``property`` (ver ``apply_account_edi_ubl_cii_res_partner_extensions``).
    """
    return {
        'peppol_endpoint': fields.Char(
            max_length=50, blank=True, default='',
            verbose_name='Peppol Endpoint',
            help_text='Identificador único usado por BIS Billing 3.0 y sus '
                      'derivados, también llamado "Endpoint ID" (Odoo '
                      'peppol_endpoint).',
        ),
        'peppol_eas': fields.Selection(
            max_length=4, choices=PEPPOL_EAS_CHOICES, blank=True, default='',
            verbose_name='Peppol e-address (EAS)',
            help_text='Código que identifica el Endpoint para BIS Billing 3.0 '
                      'y sus derivados. Lista en '
                      'https://docs.peppol.eu/poacc/billing/3.0/codelist/eas/ '
                      '(Odoo peppol_eas).',
        ),
    }


# -----------------------------------------------------------------------------
# FORMATOS UBL/CII — portados enteros (no tocan el ORM)
# -----------------------------------------------------------------------------

def _get_ubl_cii_formats(cls):
    """≙ ``_get_ubl_cii_formats`` (``odoo19c: :341-343``)."""
    return list(cls._get_ubl_cii_formats_info().keys())


def _get_ubl_cii_formats_info(cls):
    """≙ ``_get_ubl_cii_formats_info`` (``odoo19c: :345-361``) — verbatim."""
    return {
        'ubl_bis3': {
            'countries': list(PEPPOL_DEFAULT_COUNTRIES),
            'on_peppol': True,
            'sequence': 200,
            'embed_attachments': True,
        },
        'xrechnung': {'countries': ['DE'], 'sequence': 200, 'on_peppol': True},
        # Todavía no disponible por el Access Point de la referencia, aunque
        # es un formato Peppol válido.
        'ubl_a_nz': {'countries': ['NZ', 'AU'], 'on_peppol': False},
        'nlcius': {'countries': ['NL'], 'on_peppol': True},
        'ubl_sg': {'countries': ['SG'], 'on_peppol': False},  # Ídem.
        'facturx': {'countries': ['FR'], 'on_peppol': False},
        'zugferd': {'countries': ['DE'], 'on_peppol': False},
    }


def _get_ubl_cii_formats_by_country(cls):
    """≙ ``_get_ubl_cii_formats_by_country`` (``odoo19c: :363-373``)."""
    formats_info = cls._get_ubl_cii_formats_info()
    countries = {
        country
        for format_val in formats_info.values()
        for country in (format_val.get('countries') or [])
    }
    return {
        country_code: [
            format_key
            for format_key, format_val in formats_info.items()
            if country_code in (format_val.get('countries') or [])
        ]
        for country_code in countries
    }


def _get_peppol_formats(cls):
    """≙ ``_get_peppol_formats`` (``odoo19c: :404-407``)."""
    formats_info = cls._get_ubl_cii_formats_info()
    return [
        format_key
        for format_key, format_vals in formats_info.items()
        if format_vals.get('on_peppol')
    ]


def _peppol_eas_endpoint_depends(cls):
    """≙ ``_peppol_eas_endpoint_depends`` (``odoo19c: :409-412``).

    Los nombres son los de la referencia: es la lista que las localizaciones
    extienden, y cambiarlos rompería ese contrato.
    """
    return ['country_code', 'vat', 'company_registry']


# -----------------------------------------------------------------------------
# BLOQUEADOS — piezas nombradas ausentes (ver la tabla del docstring)
# -----------------------------------------------------------------------------

def _get_suggested_ubl_cii_edi_format(self):
    """≙ ``_get_suggested_ubl_cii_edi_format`` (``odoo19c: :375-389``) —
    **bloqueado**: ``commercial_partner_id`` / ``_deduce_country_code()`` /
    ``ensure_one()`` no existen (0 hits)."""
    _blocked('_get_suggested_ubl_cii_edi_format',
             'ResPartner.commercial_partner_id/_deduce_country_code/ensure_one '
             'no existen (0 hits)')


def _get_ubl_cii_edi_format(self):
    """≙ ``_get_ubl_cii_edi_format`` (``odoo19c: :391-393``) — **bloqueado**:
    orquesta ``_get_suggested_ubl_cii_edi_format``, bloqueado."""
    _blocked('_get_ubl_cii_edi_format',
             '_get_suggested_ubl_cii_edi_format esta bloqueado')


def _get_suggested_peppol_edi_format(self):
    """≙ ``_get_suggested_peppol_edi_format`` (``odoo19c: :395-398``) —
    **bloqueado**: ``commercial_partner_id``/``ensure_one`` no existen."""
    _blocked('_get_suggested_peppol_edi_format',
             'ResPartner.commercial_partner_id/ensure_one no existen (0 hits)')


def _get_peppol_edi_format(self):
    """≙ ``_get_peppol_edi_format`` (``odoo19c: :400-402``) — **bloqueado**:
    orquesta ``_get_suggested_peppol_edi_format``, bloqueado."""
    _blocked('_get_peppol_edi_format',
             '_get_suggested_peppol_edi_format esta bloqueado')


def _get_peppol_endpoint_value(self, country_code, field, eas):
    """≙ ``_get_peppol_endpoint_value`` (``odoo19c: :429-448``) —
    **bloqueado**: recorre ``self._fields`` (introspección del ORM de la
    referencia, sin análogo: este árbol usa ``Meta`` de Django)."""
    _blocked('_get_peppol_endpoint_value',
             'self._fields (introspeccion del ORM de la referencia) no tiene analogo')


def _compute_peppol_endpoint(self):
    """≙ ``_compute_peppol_endpoint`` (``odoo19c: :450-460``) —
    **bloqueado**: ``_deduce_country_code()`` (0 hits) y
    ``_get_peppol_endpoint_value``, bloqueado."""
    _blocked('_compute_peppol_endpoint',
             'ResPartner._deduce_country_code() no existe (0 hits)')


def _compute_peppol_eas(self):
    """≙ ``_compute_peppol_eas`` (``odoo19c: :462-482``) — **bloqueado**:
    misma causa que ``_compute_peppol_endpoint``."""
    _blocked('_compute_peppol_eas',
             'ResPartner._deduce_country_code() no existe (0 hits)')


def _compute_available_peppol_eas(self):
    """≙ ``_compute_available_peppol_eas`` (``odoo19c: :484-487``) —
    **bloqueado**: lee ``self._fields['peppol_eas'].selection``. La lista sí
    está aquí (:data:`PEPPOL_EAS_CHOICES`), así que el desbloqueo es de una
    línea en cuanto exista el descriptor equivalente."""
    _blocked('_compute_available_peppol_eas',
             "self._fields['peppol_eas'].selection (introspeccion del ORM de "
             "la referencia) no tiene analogo")


# -----------------------------------------------------------------------------
# COMPUTES SIN ``store`` — property
# -----------------------------------------------------------------------------

def _compute_is_ubl_format(self):
    """≙ ``_compute_is_ubl_format`` (``odoo19c: :414-418``).

    DIVERGENCIA: ``partner.invoice_edi_format`` → ``invoice_edi_format_store``,
    el ``Char`` que ``account/models/partner.py:235`` sí declara (ver "Campos"
    en el docstring del módulo).
    """
    return getattr(self, 'invoice_edi_format_store', '') in \
        type(self)._get_ubl_cii_formats()


def _compute_is_peppol_edi_format(self):
    """≙ ``_compute_is_peppol_edi_format`` (``odoo19c: :420-424``). Misma
    divergencia de nombre de campo que ``_compute_is_ubl_format``."""
    return getattr(self, 'invoice_edi_format_store', '') in \
        type(self)._get_peppol_formats()


def _available_peppol_eas(self):
    """El valor que ``available_peppol_eas`` expone — la lista completa de
    claves EAS. Es lo que la referencia calcula en
    ``_compute_available_peppol_eas`` (bloqueado, ver arriba) leyendo el
    descriptor del campo; aquí sale de :data:`PEPPOL_EAS_CHOICES`, que es la
    misma lista de la fuente."""
    return [code for code, _label in PEPPOL_EAS_CHOICES]


# -----------------------------------------------------------------------------
# VALIDACIÓN DEL ENDPOINT
# -----------------------------------------------------------------------------

def _build_error_peppol_endpoint(cls, eas, endpoint):
    """≙ ``_build_error_peppol_endpoint`` (``odoo19c: :489-503``).

    Cuatro de las cinco reglas se portan verbatim. La quinta —``eas ==
    '0009'``, SIRET francés— usa ``stdnum.fr.siret.is_valid``, y ``stdnum`` no
    es dependencia de este árbol (0 hits en ``uv.lock``). Es un **dígito de
    control**: transcribirlo a mano produciría falsos rechazos en silencio, así
    que esa rama sola levanta con la causa nombrada.
    """
    if eas == '0208' and not re.match(r"^\d{10}$", endpoint):
        return _("The Peppol endpoint is not valid. "
                 "The expected format is: 0239843188")
    if eas == '0009':
        _blocked('_build_error_peppol_endpoint (rama 0009)',
                 'stdnum.fr.siret.is_valid: stdnum no es dependencia (0 hits '
                 'en uv.lock) y es un digito de control')
    if eas == '0007' and not re.match(r"^\d{10}$", endpoint):
        return _("The Peppol endpoint is not valid. "
                 "It should contain exactly 10 digits (Company Registry number)."
                 "The expected format is: 1234567890")
    if eas == 'EM' and not single_email_re.match(endpoint):
        return _("The Peppol endpoint is not valid. A valid email is required")
    invalid_chars_re = PEPPOL_ENDPOINT_INVALID_CHARS_RE_BY_EAS.get(
        eas, PEPPOL_ENDPOINT_INVALIDCHARS_RE)
    if invalid_chars_re.search(endpoint) or not 1 <= len(endpoint) <= 50:
        return _("The Peppol endpoint (%s) is not valid. "
                 "It should contain only letters and digit.", endpoint)


def _check_peppol_fields(self):
    """≙ ``_check_peppol_fields`` (``odoo19c: :151-157``), la
    ``@api.constrains('peppol_endpoint')``.

    Se instala y se puede invocar; lo que NO se porta es su disparo automático
    al escribir (ver "``@api.constrains``" en el docstring del módulo).
    ``ValidationError`` de la referencia → ``UserError``, el equivalente de
    este árbol para un error dirigido al usuario.
    """
    if self.peppol_endpoint and self.peppol_eas:
        error = type(self)._build_error_peppol_endpoint(
            self.peppol_eas, self.peppol_endpoint)
        if error:
            raise UserError(error)


# -----------------------------------------------------------------------------
# CONSTRUCTOR EDI Y PLAN DE BÚSQUEDA
# -----------------------------------------------------------------------------

#: ≙ el ``if`` en cadena de ``_get_edi_builder`` (``odoo19c: :505-518``).
#: DIVERGENCIA: la referencia devuelve ``env['<modelo>']``; aquí los
#: constructores son clases Python planas (no modelos Django), así que
#: ``orm.registry.model_by_name`` no las ve y se devuelve la clase.
_EDI_BUILDERS = {
    'xrechnung': AccountEdiXmlUbl_De,
    # Misma plantilla para los dos formatos (Francia y Alemania).
    'facturx': AccountEdiXmlCii,
    'zugferd': AccountEdiXmlCii,
    'ubl_a_nz': AccountEdiXmlUbl_A_Nz,
    'nlcius': AccountEdiXmlUbl_Nl,
    'ubl_bis3': AccountEdiXmlUBLBIS3,
    'ubl_sg': AccountEdiXmlUbl_Sg,
}


def _get_edi_builder(cls, invoice_edi_format):
    """≙ ``_get_edi_builder`` (``odoo19c: :505-518``) — ver
    :data:`_EDI_BUILDERS` para la divergencia."""
    return _EDI_BUILDERS.get(invoice_edi_format)


def _import_retrieve_customer_from_eas_endpoint(cls, customer_values):
    """≙ ``_import_retrieve_customer_from_eas_endpoint``
    (``odoo19c: :520-530``) — verbatim: sólo compone un plan de búsqueda."""
    peppol_eas = customer_values.get('peppol_eas')
    peppol_endpoint = customer_values.get('peppol_endpoint')
    if not peppol_eas or not peppol_endpoint:
        return

    return {
        'criteria': [{
            'domain': [('peppol_eas', '=', peppol_eas),
                       ('peppol_endpoint', '=', peppol_endpoint)],
        }],
    }


def apply_account_edi_ubl_cii_res_partner_extensions():
    """Cuelga sobre ``base.ResPartner`` lo que este addon aporta — ≙
    ``_inherit = 'res.partner'``. La llama ``AccountEdiUblCiiConfig.ready()``."""
    for name, field in _extra_fields().items():
        add_field_if_absent(ResPartner, name, field)

    # Los tres ``compute`` sin ``store`` de la referencia → ``property``.
    for name, function in (
        ('is_ubl_format', _compute_is_ubl_format),
        ('is_peppol_edi_format', _compute_is_peppol_edi_format),
        ('available_peppol_eas', _available_peppol_eas),
    ):
        if not hasattr(ResPartner, name):
            setattr(ResPartner, name, property(function))

    for name, function in (
        ('_get_ubl_cii_formats', classmethod(_get_ubl_cii_formats)),
        ('_get_ubl_cii_formats_info', classmethod(_get_ubl_cii_formats_info)),
        ('_get_ubl_cii_formats_by_country',
         classmethod(_get_ubl_cii_formats_by_country)),
        ('_get_peppol_formats', classmethod(_get_peppol_formats)),
        ('_peppol_eas_endpoint_depends',
         classmethod(_peppol_eas_endpoint_depends)),
        ('_build_error_peppol_endpoint',
         classmethod(_build_error_peppol_endpoint)),
        ('_get_edi_builder', classmethod(_get_edi_builder)),
        ('_import_retrieve_customer_from_eas_endpoint',
         classmethod(_import_retrieve_customer_from_eas_endpoint)),
        ('_get_suggested_ubl_cii_edi_format', _get_suggested_ubl_cii_edi_format),
        ('_get_ubl_cii_edi_format', _get_ubl_cii_edi_format),
        ('_get_suggested_peppol_edi_format', _get_suggested_peppol_edi_format),
        ('_get_peppol_edi_format', _get_peppol_edi_format),
        ('_get_peppol_endpoint_value', _get_peppol_endpoint_value),
        ('_compute_peppol_endpoint', _compute_peppol_endpoint),
        ('_compute_peppol_eas', _compute_peppol_eas),
        ('_compute_available_peppol_eas', _compute_available_peppol_eas),
        ('_check_peppol_fields', _check_peppol_fields),
    ):
        chain_method(ResPartner, name, function)


__all__ = [
    'PEPPOL_DEFAULT_COUNTRIES',
    'PEPPOL_EAS_CHOICES',
    'UBL_CII_INVOICE_EDI_FORMATS',
    'sanitize_peppol_endpoint',
    'apply_account_edi_ubl_cii_res_partner_extensions',
]
