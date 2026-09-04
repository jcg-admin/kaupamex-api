"""Extensión de ``res.partner`` — la validación del identificador fiscal.

Adaptación de ``odoo19c: addons/base_vat/models/res_partner.py``
(``odoo-tools@622ddc2a``, LGPL-3, 981 líneas) — atribución y aviso de licencia
preservados (DEC-KX-03). Su manifiesto declara ``LGPL-3``, así que el
mecanismo es **copia + adaptación** del fuente, no reimplementación.

Porte BLOQUEADO — 59 de 64 símbolos
====================================

Los cinco que no se portan tienen su arista declarada símbolo a símbolo, y
todos apuntan a **dos** destinos medidos, no a cinco causas distintas:

- ``account.res.partner._check_vat`` y sus tres hermanos de la misma familia
  (``_run_vat_checks`` base, ``_get_vat_required_valid``,
  ``_get_country_specific_vat_variants``). La fuente los declara en
  ``odoo19c: addons/account/models/partner.py:847-959`` — **no** en ``base``,
  así que portarlos aquí sería el defecto de sitio que :ref:`h-api-568`
  registra. Medido:
  ``grep -rn "def _check_vat\b" --include=*.py src/ addons/ | grep -vc base_vat/models/res_partner.py``
  da **0**. El ``grep -v`` excluye **este** archivo: la forma sin él
  empareja esta misma cita y devolvía 1 — un reclamo que se contaba a sí
  mismo, que es lo que ``check_stale_zero_claims`` destapó.
  Sucesor: tarea **#460**.
- ``tools.hash_sign`` — la firma con la que el webhook de vuelta se autentica.
  Medido: ``grep -rc "def hash_sign" --include=*.py src/`` da **0**, y
  ``addons/account_peppol/models/account_edi_proxy_user.py:182`` ya lo
  declaraba ausente antes de este pase. Sucesor: tarea **#461**.

Los 64 se cuentan como **métodos de la clase**, que es la unidad que
``check_porte_completo`` compara. Los cuatro símbolos de módulo (``_lt``,
``_logger``, ``EU_EXTRA_VAT_CODES_INV``, ``_ref_vat``) y los veinte atributos
de clase (``_inherit``, los cuatro campos y las quince expresiones regulares
precompiladas) van **todos** portados, y se listan aparte abajo porque el gate
no los mira.

Símbolo a símbolo — los métodos
================================

.. list-table::
   :header-rows: 1
   :widths: 38 12 50

   * - Símbolo (línea de la fuente)
     - Estado
     - Nota
   * - ``_run_vat_checks`` (``:107``)
     - portado
     - la fuente lo marca ``OVERRIDE`` y **no** llama a ``super()``: se
       instala entero, sin previa que encadenar
   * - ``_inverse_vat`` (``:166``)
     - bloqueado
     - BLOQUEADO por ``account.res.partner._check_vat`` — su cuerpo es esa
       llamada y el método vive en ``account``. Sucesor: **#460**
   * - ``_onchange_vat`` (``:170``)
     - bloqueado
     - BLOQUEADO por ``account.res.partner._check_vat`` — mismo destino.
       Sucesor: **#460**
   * - ``_get_country_specific_vat_variants`` (``:174``)
     - bloqueado
     - BLOQUEADO por ``account.res.partner._run_vat_checks`` — la fuente lo
       declara en ``account``, no aquí. Sucesor: **#460**
   * - ``_compute_perform_vies_validation`` (``:186``)
     - portado
     - sirve a la ``property`` ``perform_vies_validation``
   * - ``_compute_vies_valid`` (``:198``)
     - portado
     - con una arista bloqueada declarada en su docstring
   * - ``_split_vat`` (``:214``)
     - portado
     - Python puro
   * - ``_get_iap_vies_credentials`` (``:221``)
     - portado
     - ``SystemParameter`` es el ``ir.config_parameter`` de este árbol
   * - ``_get_iap_vies_endpoint`` (``:259``)
     - portado
     - ver la divergencia 4 abajo
   * - ``_check_vies_iap`` (``:267``)
     - bloqueado
     - BLOQUEADO por ``tools.hash_sign`` — firma el ``webhook_token`` y el
       ayudante no existe en este árbol. Sucesor: **#461**
   * - ``_cron_check_vies_iap`` (``:296``)
     - portado
     - el agrupado va por el ORM de Django (divergencia 3)
   * - ``_check_vies_update_iap`` (``:309``)
     - portado
     - no necesita firma: sólo credenciales
   * - ``_update_vies_status`` (``:328``)
     - portado
     - con una arista bloqueada declarada en su docstring
   * - ``_check_vat_number`` (``:342``)
     - portado
     - **el despachador central**: método propio si existe, si no
       ``stdnum.util.get_cc_module(cc, 'vat').is_valid``
   * - ``_build_vat_error_message`` (``:349``)
     - portado
     - lee ``ResCountry.vat_label``, que existe
   * - ``check_vat_al`` (``:387``) · ``check_vat_jp`` (``:392``)
     - portados
     - delegan en ``stdnum``
   * - ``check_vat_do`` (``:400``) · ``check_vat_ro`` (``:405``)
     - portados
     - ídem, con los dos regex de personas físicas rumanas
   * - ``check_vat_gr`` (``:426``) · ``check_vat_gt`` (``:436``)
     - portados
     - conservan sus listas de VAT de prueba verbatim
   * - ``check_vat_hu`` (``:449``) · ``check_vat_ch`` (``:472``)
     - portados
     - el suizo lleva su MOD11 propio
   * - ``is_valid_ruc_ec`` (``:500``) · ``check_vat_ec`` (``:505``)
     - portados
     - Python puro
   * - ``_ie_check_char`` (``:509``) · ``check_vat_ie`` (``:522``)
     - portados
     - el guion bajo se conserva (``porte-completo-no-parcial.md``)
   * - ``check_vat_mx`` (``:533``)
     - portado
     - RFC: formato + fecha embebida, verbatim
   * - ``check_vat_no`` (``:557``) · ``check_vat_pe`` (``:585``)
     - portados
     - checksums propios
   * - ``check_vat_ph`` (``:598``) · ``check_vat_ru`` (``:601``)
     - portados
     - ídem
   * - ``check_vat_rs`` (``:639``) · ``check_vat_tr`` (``:644``)
     - portados
     - delegan en ``stdnum``
   * - ``check_vat_sa`` (``:650``) · ``check_vat_ua`` (``:657``)
     - portados
     - Python puro
   * - ``check_vat_uy`` (``:660``) · ``check_vat_uz`` (``:689``)
     - portados
     - el uruguayo lleva sus dos funciones internas verbatim
   * - ``check_vat_ve`` (``:692``) · ``check_vat_in`` (``:743``)
     - portados
     - regex con grupos condicionales / los seis GSTIN
   * - ``check_vat_br`` (``:761``) · ``check_vat_cr`` (``:781``)
     - portados
     - CPF por ``stdnum``, CNPJ propio
   * - ``check_vat_vn`` (``:792``)
     - portado
     - admite el CCCD de 12 dígitos que ``stdnum`` aún no
   * - ``format_vat_al`` (``:810``) … ``format_vat_is`` (``:856``)
     - portados
     - los ocho formateadores
   * - ``check_vat_id`` (``:862``) · ``check_vat_th`` (``:884``)
     - portados
     - el indonesio usa ``stdnum.luhn``
   * - ``check_vat_de`` (``:888``) · ``check_vat_il`` (``:893``)
     - portados
     - delegan en ``stdnum``
   * - ``check_vat_ma`` (``:897``) · ``format_vat_sm`` (``:900``)
     - portados
     - Python puro / ``stdnum``
   * - ``check_vat_tw`` (``:904``)
     - portado
     - la regla de 2025 (división entre 5), que ``stdnum`` no trae
   * - ``_format_vat_number`` (``:936``)
     - portado
     - el despachador de formato, hermano de ``_check_vat_number``
   * - ``_convert_hu_local_to_eu_vat`` (``:947``)
     - portado
     - Python puro
   * - ``_get_vat_required_valid`` (``:952``)
     - bloqueado
     - BLOQUEADO por ``account.res.partner._get_vat_required_valid`` — su
       cuerpo abre con ese ``super()``. Sucesor: **#460**
   * - ``create`` (``:964``) · ``write`` (``:970``)
     - portados
     - un solo ``overrides={'save': …}``: aquí la mutación tiene una entrada,
       no dos. Divergencia de mecanismo declarada en el docstring de ``save``
   * - ``_create_contact_parent_company`` (``:976``)
     - portado
     - ``overrides=``; la previa existe
       (``src/addons/base/models/res_partner.py:1777``)

Símbolos que el gate NO cuenta, y que también van portados
===========================================================

**Módulo (4 de 4):** ``_lt`` (``:19``), ``_logger`` (``:20``),
``EU_EXTRA_VAT_CODES_INV`` (``:23``) y ``_ref_vat`` (``:25-89``) — los 86
ejemplos de formato, verbatim.

**Atributos de clase (20 de 20):** ``_inherit`` (``:92``); los cuatro campos
``vies_valid`` (``:94``), ``perform_vies_validation`` (``:101``),
``country_id`` (``:103``) y ``vat`` (``:104``); y las quince expresiones
regulares precompiladas (``:385``, ``:397``, ``:398``, ``:434``, ``:445``,
``:446``, ``:447``, ``:470``, ``:527``, ``:596``, ``:647``, ``:759``,
``:779``, ``:789``, ``:790``).

Divergencias declaradas — de mecanismo, no de alcance
======================================================

1. **``inverse="_inverse_vat"`` no viaja en la redeclaración del campo.** La
   fuente redeclara ``country_id`` y ``vat`` sólo para colgarles el
   ``inverse``, que es su forma de decir «al escribir esto, valida». Aquí el
   campo ya existe en ``base.ResPartner`` (``:386`` y ``:459``) y el
   ``inverse`` no tiene análogo: la validación al escribir la lleva el
   validador de campo de Django (ver la divergencia 2). Los dos campos
   **existen y no se redeclaran** — redeclararlos duplicaría la columna.
2. **``validate_rfc`` sigue enganchado al campo ``vat``.** Es un artefacto
   **local**, sin contraparte en la fuente: ``addons/base_vat/validators.py``
   no existe en ``odoo19c: addons/base_vat/``. Se conserva porque es el único
   punto de este árbol donde el RFC se valida **al guardar** —el ``inverse``
   de la fuente— y porque tiene consumidores vivos
   (``tests/integration/company/test_base_vat.py``). Reconciliarlo con
   ``check_vat_mx``, que es el símbolo de la fuente y aplica el mismo criterio
   (formato + fecha), es la tarea **#462**.
3. **El agrupado de ``_cron_check_vies_iap`` va por el ORM de Django.** La
   fuente usa ``self._read_group(groupby=['vat'], aggregates=['id:recordset'])``;
   medido, este árbol no declara ese agregador
   (``grep -rc "def _read_group" --include=*.py src/orm/`` da **0**). El
   equivalente es un ``filter(vat__in=…)`` por VAT, que produce la misma
   partición: los partners de cada VAT reciben su estado.
4. **El endpoint de VIES es un servicio de Odoo S.A.** ``vies.api.odoo.com`` /
   ``vies.test.odoo.com`` se portan **verbatim** porque son el valor por
   defecto del parámetro ``iap_vies.endpoint``, no una constante del código:
   quien opere esta plataforma lo reemplaza por el suyo sin tocar el archivo.
   Y nada lo llama mientras ninguna empresa encienda ``vat_check_vies``, que
   nace en ``False`` (``models/res_company.py``).
5. **``@api.model`` / ``@api.depends`` / ``@api.onchange`` no se decoran.** Son
   los marcadores del motor de computados de la fuente. Aquí el campo con
   ``store`` es una columna y el sin ``store`` es una ``property``: no hay cola
   de recomputación que anotar. ``_compute_vies_valid`` se invoca desde
   ``_cron_check_vies_iap`` y desde quien escriba el VAT.

Lo que este archivo no cierra
==============================

Los cinco símbolos bloqueados de arriba (sucesores **#460** y **#461**) y la
reconciliación de ``validators.py`` con ``check_vat_mx`` (**#462**).
"""
import datetime
import logging
import re
import secrets
import uuid

import requests
import stdnum
import stdnum.util
from stdnum import luhn
from stdnum.exceptions import InvalidChecksum, InvalidFormat
from stdnum.util import clean

import fields
from addons.base.models.ir_config_parameter import SystemParameter
from addons.base.models.ir_module import IrModule
from addons.base.models.res_company import ResCompany
from addons.base.models.res_country import ResCountry
from addons.base.models.res_country_group import ResCountryGroup
from addons.base.models.res_partner import EU_EXTRA_VAT_CODES
from addons.base_vat.validators import validate_rfc
from exceptions import ValidationError
from orm.environments import env, get_context, get_current_company, sudo
from orm.model_classes import extend_model
from tools.translate import _

#: ≙ ``_lt = LazyTranslate(__name__)`` (``odoo19c: :19``). El ``_`` de este
#: árbol **ya es perezoso** —``tools/translate.py`` lo construye sobre
#: ``django.utils.functional.lazy``—, así que el alias es el mismo mecanismo
#: con otro nombre y no una segunda implementación.
_lt = _

_logger = logging.getLogger(__name__)

#: ≙ ``EU_EXTRA_VAT_CODES_INV`` (``odoo19c: :23``) — el prefijo de IVA de
#: vuelta a su código de país (``EL`` → ``GR``, ``XI`` → ``GB``).
EU_EXTRA_VAT_CODES_INV = {v: k for k, v in EU_EXTRA_VAT_CODES.items()}

#: El nombre del modelo que la fuente declara en su ``_inherit`` (``:92``).
_inherit = 'res.partner'

#: ≙ ``_ref_vat`` (``odoo19c: :25-89``) — el ejemplo de formato por país que
#: el mensaje de error cita. Verbatim, con sus comentarios de autoría.
_ref_vat = {
    'al': 'ALJ91402501L',
    'ar': '20055361682',
    'at': 'ATU12345675',
    'au': '83 914 571 673',
    'be': 'BE0477472701',
    'bg': 'BG1234567892',
    'br': _lt('either 11 digits for CPF or 14 characters for CNPJ'),
    'cr': '3101012009',
    'ch': _lt('CHE-123.456.788 TVA or CHE-123.456.788 MWST or CHE-123.456.788 IVA'),  # Swiss by Yannick Vaucher @ Camptocamp
    'cl': '76086428-5',
    'co': '213123432-1',
    'cy': 'CY10259033P',
    'cz': 'CZ12345679',
    'de': _lt('DE123456788 or 12/345/67890'),
    'dk': 'DK12345674',
    'do': _lt('1-01-85004-3 or 101850043'),
    'ec': _lt('1792060346001 or 1792060346'),
    'ee': 'EE123456780',
    'es': 'ESA12345674',
    'fi': 'FI12345671',
    'fr': 'FR23334175221',
    'gb': _lt('GB123456782 or XI123456782'),
    'gr': 'EL123456783',
    'hu': _lt('HU12345676 or 12345678-1-11 or 8071592153'),
    'hr': 'HR01234567896',  # Croatia, contributed by Milan Tribuson
    'id': '1234567890123456',
    'ie': 'IE1234567FA',
    'il': _lt('XXXXXXXXX [9 digits] and it should respect the Luhn algorithm checksum'),
    'in': "12AAAAA1234AAZA",
    'is': 'IS062199',
    'it': 'IT12345670017',
    'jp': 'T7000012050002',
    'kr': '123-45-67890 or 1234567890',
    'lt': 'LT123456715',
    'lu': 'LU12345613',
    'lv': 'LV41234567891',
    'ma': '12345678',
    'mc': 'FR53000004605',
    'mt': 'MT12345634',
    'mx': _lt('GODE561231GR8'),
    'nl': 'NL123456782B90',
    'no': 'NO123456785',
    'nz': _lt('49-098-576 or 49098576'),
    'pe': _lt('10XXXXXXXXY or 20XXXXXXXXY or 15XXXXXXXXY or 16XXXXXXXXY or 17XXXXXXXXY'),
    'ph': '123-456-789-123',
    'pl': 'PL1234567883',
    'pt': 'PT123456789',
    'ro': 'RO1234567897 or 8001011234567 or 9000123456789',
    'rs': 'RS101134702',
    'ru': '123456789047',
    'se': 'SE123456789701',
    'si': 'SI12345679',
    'sk': 'SK2022749619',
    'sm': 'SM24165',
    'th': '1234545678781',
    'tr': _lt('11111111111 (NIN) or 2222222222 (VKN)'),
    'ua': _lt('12345678 or UA12345678 (EDRPOU), 1234567890 (RNOPP) or 123456789012 (IPN)'),
    'uy': _lt("Example: '219999830019' (format: 12 digits, all numbers, valid check digit)"),
    'uz': _lt('XXXXXXXXX [9 digits]'),
    've': 'V-12345678-1, V123456781, V-12.345.678-1',
    'xi': 'XI123456782',
    'sa': _lt('310175397400003 [Fifteen digits, first and last digits should be "3"]'),
}

# === Las quince expresiones regulares precompiladas =======================
# La fuente las declara como atributos de clase; aquí son constantes de módulo
# y se cuelgan igual sobre el modelo (ver ``apply_base_vat_extensions``), para
# que ``self._check_vat_ch_re`` siga resolviendo como allá.

_check_vat_al_re = re.compile(r'^[JKLM][0-9]{8}[A-Z]$')
_check_tin1_ro_natural_persons = re.compile(r'[1-9]\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{6}')
_check_tin2_ro_natural_persons = re.compile(r'9000\d{9}')
# Our EDI provider Infile has designated this range of testing VATs for our customers.
_check_vat_gt_testing_infile = re.compile(r'98[0-9]{10}K')
_check_tin_hu_individual_re = re.compile(r'^8\d{9}$')
_check_tin_hu_companies_re = re.compile(r'^\d{8}-?[1-5]-?\d{2}$')
_check_tin_hu_european_re = re.compile(r'^\d{8}$')
_check_vat_ch_re = re.compile(r'E([0-9]{9}|-[0-9]{3}\.[0-9]{3}\.[0-9]{3})( )?(MWST|TVA|IVA)$')
# Mexican VAT verification, contributed by Vauxoo
# and Panos Christeas <p_christ@hol.gr>
_check_vat_mx_re = re.compile(r"(?P<primeras>[A-Za-z\xd1\xf1&]{3,4})"
                              r"[ \-_]?"
                              r"(?P<ano>[0-9]{2})(?P<mes>[01][0-9])(?P<dia>[0-3][0-9])"
                              r"[ \-_]?"
                              r"(?P<code>[A-Za-z0-9&\xd1\xf1]{3})")
# Philippines TIN (+ branch code) validation
_check_vat_ph_re = re.compile(r"\d{3}-\d{3}-\d{3}(-\d{3,5})?$")
_check_vat_sa_re = re.compile(r"^3[0-9]{13}3$")
# Minimal regex matching similar to stdnum
# Derived from https://github.com/arthurdejong/python-stdnum/commit/d3ec3bd7fefe0d0a708b6594a66de28777eb9b8d
_check_vat_br_re = re.compile(r'^[\dA-Z]+$')
_check_vat_cr_re = re.compile(r'^(?:[1-9]\d{8}|\d{10}|[1-9]\d{10,11})$')
_check_vat_vn_re = re.compile(r'^\d{10}(?:-?\d{3})?$|^\d{12}$')
_check_vat_vn_companies_re = re.compile(r'^\d{10}(?:-?\d{3})?$')

#: El endpoint de producción y el de pruebas del proxy VIES — ``odoo19c: :260``.
IAP_VIES_ENDPOINTS = ('https://vies.api.odoo.com', 'https://vies.test.odoo.com')

#: Las dos claves con que el proxy identifica a esta base — ``odoo19c: :232``.
IAP_CLIENT_IDENTIFIER_PARAM = 'iap_vies.client_identifier'
IAP_CLIENT_TOKEN_PARAM = 'iap_vies.client_token'
IAP_ENDPOINT_PARAM = 'iap_vies.endpoint'


# === El bloque de VIES ====================================================

def _compute_perform_vies_validation(self):
    """≙ ``_compute_perform_vies_validation`` (``odoo19c: :186-197``).

    Docstring de la fuente, verbatim: *"Determine whether to show VIES
    validity on the current VAT number"*.
    """
    to_check = self.vat
    company = _current_company()
    company_code = ''
    if company is not None:
        fiscal_country = getattr(company, 'account_fiscal_country', None)
        country = getattr(company, 'country', None)
        company_code = getattr(fiscal_country, 'code', None) or getattr(
            country, 'code', '') or ''
    return bool(
        to_check
        and not to_check[:2].upper() == company_code
        and company is not None
        and getattr(company, 'vat_check_vies', False)
    )


def _compute_vies_valid(self):
    """≙ ``_compute_vies_valid`` (``odoo19c: :198-213``).

    Docstring de la fuente, verbatim: *"Check the VAT number with VIES, if
    enabled."*

    BLOQUEADO por ``tools.hash_sign`` — razón: la rama que consulta de verdad
    llama a :func:`_check_vies_iap`, que necesita firmar el ``webhook_token``
    y ese ayudante no existe en este árbol (medido en el encabezado del
    módulo: 0 definiciones). Sucesor: tarea **#461**. Las dos ramas que **no**
    consultan —ninguna empresa con la casilla encendida, y el partner que
    hereda del padre— sí hacen lo que la fuente hace.
    """
    with sudo():
        enabled = _companies_with_vies_check().exists()
    if not enabled:
        self.vies_valid = False
        return False
    if not self.vat:
        self.vies_valid = False
        return False
    if self.parent and self.parent.vat == self.vat:
        self.vies_valid = self.parent.vies_valid
        return self.vies_valid
    status = self._check_vies_iap()
    self._update_vies_status(status)
    return self.vies_valid


def _companies_with_vies_check():
    """Las empresas con ``vat_check_vies`` encendido — ≙ el ``search_count``
    de ``_compute_vies_valid`` (``odoo19c: :200``).

    La fuente cuenta sobre ``res.company`` sin acotar por la empresa activa
    (``self.env['res.company'].sudo().search_count([('vat_check_vies','=',True)])``);
    aquí es la misma población, y el ``sudo()`` lo pone el llamador.
    """
    return ResCompany.objects.filter(vat_check_vies=True)


def _split_vat(self, vat):
    """≙ ``_split_vat`` (``odoo19c: :214-219``) — prefijo y número."""
    vat_prefix, vat_number = vat[:2].upper(), vat[2:].replace(' ', '')
    if not vat_prefix.isalpha():
        return '', vat
    return vat_prefix, vat_number


def _get_iap_vies_credentials(self):
    """≙ ``_get_iap_vies_credentials`` (``odoo19c: :221-256``).

    Docstring de la fuente, verbatim: *"Return a couple (identifier, token)
    that is going to identify this db to IAP such that only this one can
    request updates on a previously asked VIES check. If they exist, we simply
    return them. If they don't, we create them in another cursor to avoid the
    current transaction to be rolled back after in case of an uncaucht error
    while the credentials have been registered on IAP."*

    Divergencia declarada: **el segundo cursor no se abre.** La fuente lo usa
    para que el alta de credenciales sobreviva a un rollback de la transacción
    en curso; aquí ``SystemParameter.set_param`` escribe con el ORM de Django
    y la conexión es la misma, así que abrir otra sería inventar una
    transacción que este stack no gestiona. La relectura tras el alta —la
    guarda de concurrencia de la fuente— sí se conserva.
    """
    identifier = SystemParameter.get_param(IAP_CLIENT_IDENTIFIER_PARAM)
    token = SystemParameter.get_param(IAP_CLIENT_TOKEN_PARAM)
    if identifier and token:
        return identifier, token

    identifier = str(uuid.uuid4())
    token = secrets.token_urlsafe()
    SystemParameter.set_param(IAP_CLIENT_IDENTIFIER_PARAM, identifier)
    SystemParameter.set_param(IAP_CLIENT_TOKEN_PARAM, token)
    return (SystemParameter.get_param(IAP_CLIENT_IDENTIFIER_PARAM),
            SystemParameter.get_param(IAP_CLIENT_TOKEN_PARAM))


def _get_iap_vies_endpoint(self):
    """≙ ``_get_iap_vies_endpoint`` (``odoo19c: :259-265``).

    La fuente elige el de pruebas cuando el módulo se instaló con datos de
    demostración. Aquí el parámetro manda igual, y el mismo ``UserError`` de
    allá protege contra apuntar a un tercero cualquiera.
    """
    prod, test = IAP_VIES_ENDPOINTS
    default_endpoint = test if _base_vat_module_is_demo() else prod
    endpoint = SystemParameter.get_param(IAP_ENDPOINT_PARAM, default_endpoint)
    if endpoint not in IAP_VIES_ENDPOINTS:
        raise ValidationError(_('Invalid IAP VIES endpoint'))
    return endpoint


def _current_company():
    """La empresa en curso como **objeto** — ≙ ``self.env.company``.

    ``get_current_company()`` devuelve la **PK** (``orm/environments.py:233``),
    no el registro; la referencia lee atributos (``account_fiscal_country_id``,
    ``vat_check_vies``) sobre el objeto, así que aquí se resuelve una vez.
    ``None`` cuando no hay empresa activada, que es el ``env.company`` vacío.
    """
    company_id = get_current_company()
    if company_id is None:
        return None
    return ResCompany.objects.filter(pk=company_id).first()


def _base_vat_module_is_demo():
    """≙ ``self.env.ref('base.module_base_vat').demo`` (``odoo19c: :261``)."""
    row = IrModule.objects.filter(name='base_vat').first()
    return bool(getattr(row, 'demo', False))


def _check_vies_iap(self):
    """BLOQUEADO por ``tools.hash_sign`` — razón: el cuerpo firma el
    ``webhook_token`` con ``hash_sign(self.sudo().env, "vies_check", self.vat,
    expiration_hours=24 * 7)`` (``odoo19c: :285``) y ese ayudante no existe en
    este árbol; medido en el encabezado del módulo, 0 definiciones. Sin la
    firma el proxy no puede devolver el resultado y el par
    ``webhook_update_vies`` queda abierto. Sucesor: tarea **#461**.

    Docstring de la fuente, verbatim: *"Called when VAT is manually edited to
    query IAP for the validity of the VAT"*.
    """
    raise NotImplementedError(
        '_check_vies_iap está bloqueado: tools.hash_sign no existe en este '
        'árbol y sin él el webhook de vuelta no se puede autenticar '
        '(tarea #461).')


def _cron_check_vies_iap(self):
    """≙ ``_cron_check_vies_iap`` (``odoo19c: :296-307``).

    Docstring de la fuente, verbatim: *"Called by cron to check if IAP has any
    update on a previously requested VAT that was pending"*.
    """
    vat_to_status = self._check_vies_update_iap()
    _logger.info("IAP VIES check response: %s", vat_to_status)
    model = type(self)
    for vat, status in vat_to_status.items():
        for partner in model.objects.filter(vat=vat):
            partner._update_vies_status(status)


def _check_vies_update_iap(self):
    """≙ ``_check_vies_update_iap`` (``odoo19c: :309-326``).

    Docstring de la fuente, verbatim: *"Calls IAP for an update of a
    previously requested VAT validity"*.
    """
    client_identifier, client_token = self._get_iap_vies_credentials()
    try:
        req = requests.post(
            self._get_iap_vies_endpoint() + '/api/vies/1/check_update',
            data={
                "db_uuid": SystemParameter.get_param('database.uuid'),
                "client_identifier": client_identifier,
                "client_token": client_token,
            },
            timeout=10,
        )
        req.raise_for_status()
        return req.json()
    except requests.exceptions.RequestException:
        _logger.exception("Error while contacting IAP VIES")
    return {}


def _update_vies_status(self, status):
    """≙ ``_update_vies_status`` (``odoo19c: :328-340``).

    BLOQUEADO por ``mail.thread._message_log_batch`` — razón: la nota que la
    fuente deja en el hilo del partner necesita ese método y no existe en este
    árbol (medido: ``grep -rn "def _message_log_batch" --include=*.py src/ addons/ | grep -vc base_vat/models/res_partner.py``
    da **0** — el ``grep -v`` excluye este archivo para que la cita no se
    cuente a sí misma; ``addons/crm/models/crm_team.py:140`` ya lo declaraba
    ausente). La escritura del estado —el trabajo del método— sí se hace.
    Sucesor: tarea **#462**.
    """
    self.vies_valid = status == "valid"
    self.save(update_fields=['vies_valid'])
    _logger.info("VIES status updated to %s for partner ids: %s",
                 status, [self.pk])
    return self.vies_valid


# === Los dos despachadores ================================================

def _check_vat_number(self, country_code, vat_number):
    """≙ ``_check_vat_number`` (``odoo19c: :342-347``).

    Comentario de la fuente, verbatim: *"Low-level method directly calling
    stdnum or our own specific method."*

    Es **el** símbolo del addon: el método propio del país gana, y sólo cuando
    no hay ninguno se cae a ``stdnum``. Por eso los ``check_vat_xx`` de este
    archivo son la excepción y no la regla.
    """
    check_func_name = 'check_vat_' + country_code.lower()
    check_func = getattr(self, check_func_name, None) or getattr(
        stdnum.util.get_cc_module(country_code, 'vat'), 'is_valid', None)
    return check_func(vat_number) if check_func else True


def _format_vat_number(self, country_code, vat):
    """≙ ``_format_vat_number`` (``odoo19c: :936-945``).

    Comentario de la fuente, verbatim: *"Low-level method directly calling
    stdnum or our own specific method returning the formatted VAT."*
    """
    stdnum_vat_fix_func = getattr(
        stdnum.util.get_cc_module(country_code, 'vat'), 'compact', None)
    # If any localization module needs to define vat fix method for its country
    # then we give first priority to it.
    format_func_name = 'format_vat_' + country_code.lower()
    format_func = getattr(self, format_func_name, None) or stdnum_vat_fix_func
    if format_func:
        vat = format_func(vat)
    return vat


def _build_vat_error_message(self, country_code, wrong_vat, record_label):
    """≙ ``_build_vat_error_message`` (``odoo19c: :349-383``)."""
    company = _current_company()

    vat_label = _("VAT")
    country = getattr(company, 'country', None) if company is not None else None
    if (country_code and country is not None
            and country_code == country.code and country.vat_label):
        vat_label = country.vat_label

    expected_format = _ref_vat.get(country_code.lower())
    expected_note = ""
    if expected_format:
        expected_note = ' \n' + _(
            'Note: the expected format is %(expected_format)s',
            expected_format=expected_format)

    # Catch use case where the record label is about the public user (name: False)
    if 'False' not in record_label:
        return '\n' + _(
            'The %(vat_label)s number [%(wrong_vat)s] for %(record_label)s '
            'does not seem to be valid. %(expected_note)s',
            vat_label=vat_label, wrong_vat=wrong_vat,
            record_label=record_label, expected_note=expected_note)
    return '\n' + _(
        'The %(vat_label)s number [%(wrong_vat)s] does not seem to be valid. '
        '%(expected_note)s',
        vat_label=vat_label, wrong_vat=wrong_vat,
        expected_note=expected_note)


def _run_vat_checks(self, country, vat, partner_name='', validation='error'):
    """≙ ``_run_vat_checks`` (``odoo19c: :107-164``).

    Docstring de la fuente, verbatim: *"OVERRIDE"* — y **no llama a
    ``super()``**: reemplaza entero al de ``account``, así que se instala sin
    previa que encadenar.

    Devuelve ``(vat_a_guardar, codigo_de_pais_comprobado)``.
    """
    if not country or not vat:
        return vat, False
    if len(vat) == 1:
        if vat == '/' or not validation:
            return vat, False
        if validation == 'setnull':
            return '', False
        if validation == 'error':
            raise ValidationError(
                _("To explicitly indicate no (valid) VAT, use '/' instead. "))
    vat_prefix, vat_number = self._split_vat(vat)

    europe = _europe_country_group()
    if vat_prefix == 'EU' and (europe is None
                               or country not in europe.country_ids.all()):
        # Foreign companies that trade with non-enterprises in the EU
        # may have a VATIN starting with "EU" instead of a country code.
        return vat, False

    do_eu_check = False
    prefixed_country = ''
    eu_prefix_country_group = ResCountryGroup.objects.filter(
        code='EU_PREFIX').first()
    country_code = EU_EXTRA_VAT_CODES_INV.get(vat_prefix, vat_prefix)
    prefix_codes = ([c.code for c in eu_prefix_country_group.country_ids.all()]
                    if eu_prefix_country_group else [])
    if country_code in prefix_codes:
        if 'EU_PREFIX' in country.country_group_codes and vat_prefix:
            vat = vat_number
            prefixed_country = vat_prefix
        else:
            do_eu_check = True

    code_to_check = prefixed_country or country.code
    vat = self._format_vat_number(code_to_check, vat)

    if prefixed_country == 'GR':
        prefixed_country = 'EL'

    vat_to_return = prefixed_country + vat

    # The context key 'no_vat_validation' allows you to store/set a VAT number
    # without doing validations. This is for API pushes from external platforms
    # where you have no control over VAT numbers.
    if not validation or _no_vat_validation():
        return vat_to_return, code_to_check

    # Avoid validating double prefix like BEBE0477472701
    double_prefix = prefixed_country and vat_to_return.startswith(
        prefixed_country + prefixed_country)
    if not self._check_vat_number(code_to_check, vat) or double_prefix:
        partner_label = _("partner [%s]", partner_name)
        if do_eu_check:
            other = ResCountry.objects.filter(code=country_code).first()
            try:
                return self._run_vat_checks(
                    other, vat_prefix + vat_number, partner_name, validation)
            except ValidationError:
                msg = self._build_vat_error_message(
                    code_to_check, vat, partner_label)
                raise ValidationError(
                    msg + "\n\n" + _('If you are trying to input a European '
                                     'number, this is the expected format: ')
                    + str(_ref_vat[country_code.lower()]))
        if validation == 'error':
            msg = self._build_vat_error_message(
                code_to_check, vat, partner_label)
            raise ValidationError(msg)
        return '', code_to_check
    return vat_to_return, code_to_check


def _europe_country_group():
    """≙ ``self.env.ref('base.europe')`` (``odoo19c: :117``)."""
    return ResCountryGroup.objects.filter(name='Europe').first()


def _no_vat_validation():
    """≙ ``self.env.context.get('no_vat_validation')`` (``odoo19c: :138``)."""
    return bool(get_context().get('no_vat_validation'))


# === Los cinco bloqueados =================================================

def _inverse_vat(self):
    """BLOQUEADO por ``account.res.partner._check_vat`` — razón: el cuerpo de
    la fuente es ``self._check_vat()`` y ese método vive en
    ``odoo19c: addons/account/models/partner.py:847``, no en ``base``; medido
    en el encabezado del módulo, 0 definiciones en este árbol. Portarlo aquí
    sería el defecto de sitio de :ref:`h-api-568`. Sucesor: tarea **#460**.
    """
    raise NotImplementedError(
        '_inverse_vat está bloqueado: res.partner._check_vat no existe en '
        'este árbol; su hogar es el addon account (tarea #460).')


def _onchange_vat(self):
    """BLOQUEADO por ``account.res.partner._check_vat`` — razón: misma
    medición que :func:`_inverse_vat`; el cuerpo es
    ``self._check_vat(validation=False)``. Sucesor: tarea **#460**.
    """
    raise NotImplementedError(
        '_onchange_vat está bloqueado: res.partner._check_vat no existe en '
        'este árbol (tarea #460).')


def _get_country_specific_vat_variants(self, normalized_vat, country_prefix):
    """BLOQUEADO por ``account.res.partner._get_country_specific_vat_variants``
    — razón: la fuente **empieza** por ``super()`` y añade las tres variantes
    suizas al resultado; sin la previa no hay a qué añadir. Medido en el
    encabezado del módulo: 0 definiciones. Sucesor: tarea **#460**.
    """
    raise NotImplementedError(
        '_get_country_specific_vat_variants está bloqueado: su super() vive '
        'en account.res.partner y no existe en este árbol (tarea #460).')


def _get_vat_required_valid(self, company=None):
    """BLOQUEADO por ``account.res.partner._get_vat_required_valid`` — razón:
    la fuente lo marca ``OVERRIDE`` y **combina** con ``super()``
    (``vat_required_valid and self.vies_valid``); sin la previa el ``and`` no
    tiene primer operando. Medido en el encabezado del módulo: 0 definiciones.
    Sucesor: tarea **#460**.
    """
    raise NotImplementedError(
        '_get_vat_required_valid está bloqueado: su super() vive en '
        'account.res.partner y no existe en este árbol (tarea #460).')


# === Los validadores por país =============================================

def check_vat_al(self, vat):
    """Check Albania VAT number"""
    number = stdnum.util.get_cc_module('al', 'vat').compact(vat)
    return len(number) == 10 and bool(_check_vat_al_re.match(number))


def check_vat_jp(self, vat):
    """≙ ``check_vat_jp`` (``odoo19c: :392-395``)."""
    if vat and vat[0] == 'T':
        vat = vat[1:]
    return stdnum.util.get_cc_module('jp', 'vat').is_valid(vat)


def check_vat_do(self, vat):
    """≙ ``check_vat_do`` (``odoo19c: :400-403``)."""
    is_valid_vat = stdnum.util.get_cc_module("do", "vat").is_valid
    is_valid_cedula = stdnum.util.get_cc_module("do", "cedula").is_valid
    return is_valid_vat(vat) or is_valid_cedula(vat)


def check_vat_ro(self, vat):
    """Check Romanian VAT number that can be for example 'RO1234567897 or
    'xyyzzaabbxxxx' or '9000xxxxxxxx'.

    - For xyyzzaabbxxxx, 'x' can be any number, 'y' is the two last digit of a
      year (in the range 00…99), 'a' is a month, b is a day of the month, the
      number 8 and 9 are Country or district code (For those twos digits, we
      decided to let some flexibility to avoid complexifying the regex and
      also for maintainability)
    - 9000xxxxxxxx, start with 9000 and then is filled by number In the range 0...9

    Also stdum also checks the CUI or CIF (Romanian company identifier). So a
    number like '123456897' will pass.
    """
    if _check_tin1_ro_natural_persons.match(vat):
        return True
    if _check_tin2_ro_natural_persons.match(vat):
        return True
    # Check the vat number
    return stdnum.util.get_cc_module('ro', 'vat').is_valid(vat)


def check_vat_gr(self, vat):
    """Allows some custom test VAT number to be valid to allow testing Greece EDI."""
    greece_test_vats = ('047747270', '047747210', '047747220', '117747270',
                        '127747270')
    if vat in greece_test_vats:
        return True
    return stdnum.util.get_cc_module('gr', 'vat').is_valid(vat)


def check_vat_gt(self, vat):
    """Allow some custom Guatemala NIT numbers to pass the test to be used for
    testing the Guatemalan EDI."""
    guatemalan_test_vats = ('11201220K', '11201350K')
    if vat in guatemalan_test_vats or _check_vat_gt_testing_infile.match(vat):
        return True
    return stdnum.util.get_cc_module('gt', 'vat').is_valid(vat)


def check_vat_hu(self, vat):
    """Check Hungary VAT number that can be for example 'HU12345676 or
    'xxxxxxxx-y-zz' or '8xxxxxxxxy'

    - For xxxxxxxx-y-zz, 'x' can be any number, 'y' is a number between 1 and 5
      depending on the person and the 'zz' is used for region code.
    - 8xxxxxxxxy, Tin number for individual, it has to start with an 8 and
      finish with the check digit
    - In case of EU format it will be the first 8 digits of the full VAT
    """
    if _check_tin_hu_companies_re.match(vat):
        return True
    if _check_tin_hu_individual_re.match(vat):
        return True
    if _check_tin_hu_european_re.match(vat):
        return True
    # Check the vat number
    return stdnum.util.get_cc_module('hu', 'vat').is_valid(vat)


def check_vat_ch(self, vat):
    """Check Switzerland VAT number.

    A new VAT number format in Switzerland has been introduced between 2011
    and 2013. The old format "TVA 123456" is not valid since 2014. Accepted
    format are (spaces are ignored): CHE#########MWST / TVA / IVA and
    CHE-###.###.### MWST / TVA / IVA.

    /!\\ The english abbreviation VAT is not valid /!\\
    """
    match = _check_vat_ch_re.match(vat)
    if match:
        # For new TVA numbers, the last digit is a MOD11 checksum digit build
        # with weighting pattern: 5,4,3,2,7,6,5,4
        num = [s for s in match.group(1) if s.isdigit()]   # get the digits only
        factor = (5, 4, 3, 2, 7, 6, 5, 4)
        csum = sum(int(num[i]) * factor[i] for i in range(8))
        check = (11 - (csum % 11)) % 11
        return check == int(num[8])
    return False


def is_valid_ruc_ec(self, vat):
    """≙ ``is_valid_ruc_ec`` (``odoo19c: :500-503``)."""
    if len(vat) in (10, 13) and vat.isdecimal():
        return True
    return False


def check_vat_ec(self, vat):
    """≙ ``check_vat_ec`` (``odoo19c: :505-507``)."""
    vat = clean(vat, ' -.').upper().strip()
    return self.is_valid_ruc_ec(vat)


def _ie_check_char(self, vat):
    """≙ ``_ie_check_char`` (``odoo19c: :509-520``).

    El guion bajo se conserva: es el contrato de visibilidad que la fuente
    declara (``porte-completo-no-parcial.md``).
    """
    vat = vat.zfill(8)
    extra = 0
    if vat[7] not in ' W':
        if vat[7].isalpha():
            extra = 9 * (ord(vat[7]) - 64)
        else:
            # invalid
            return -1
    checksum = extra + sum((8 - i) * int(x) for i, x in enumerate(vat[:7]))
    return 'WABCDEFGHIJKLMNOPQRSTUV'[checksum % 23]


def check_vat_ie(self, vat):
    """≙ ``check_vat_ie`` (``odoo19c: :521-523``). La fuente lo marca
    ``# TODO: remove in master`` — el comentario se conserva porque es el
    estado del símbolo allá, no una nota nuestra."""
    return stdnum.util.get_cc_module('ie', 'vat').is_valid(vat)


def check_vat_mx(self, vat):
    """Mexican VAT verification

    Verificar RFC México
    """
    m = _check_vat_mx_re.fullmatch(vat)
    if not m:
        # No valid format
        return False
    year = int(m['ano'])
    if year > 30:
        year = 1900 + year
    else:
        year = 2000 + year
    try:
        datetime.date(year, int(m['mes']), int(m['dia']))
    except ValueError:
        return False

    # Valid format and valid date
    return True


def check_vat_no(self, vat):
    """Check Norway VAT number. See http://www.brreg.no/english/coordination/number.html

    Norway VAT validation, contributed by Rolv Råen (adEgo) <rora@adego.no>.
    Support for MVA suffix contributed by Bringsvor Consulting AS.
    """
    if len(vat) == 12 and vat.upper().endswith('MVA'):
        vat = vat[:-3]  # Strictly speaking we should enforce the suffix MVA but...

    if len(vat) != 9:
        return False
    try:
        int(vat)
    except ValueError:
        return False

    total = (3 * int(vat[0])) + (2 * int(vat[1])) + \
        (7 * int(vat[2])) + (6 * int(vat[3])) + \
        (5 * int(vat[4])) + (4 * int(vat[5])) + \
        (3 * int(vat[6])) + (2 * int(vat[7]))

    check = 11 - (total % 11)
    if check == 11:
        check = 0
    if check == 10:
        # 10 is not a valid check digit for an organization number
        return False
    return check == int(vat[8])


def check_vat_pe(self, vat):
    """Peruvian VAT validation, contributed by Vauxoo."""
    if len(vat) != 11 or not vat.isdigit():
        return False
    dig_check = 11 - (sum(int('5432765432'[f]) * int(vat[f])
                          for f in range(0, 10)) % 11)
    if dig_check == 10:
        dig_check = 0
    elif dig_check == 11:
        dig_check = 1
    return int(vat[10]) == dig_check


def check_vat_ph(self, vat):
    """≙ ``check_vat_ph`` (``odoo19c: :598-599``)."""
    return (len(vat) >= 11 and len(vat) <= 17
            and bool(_check_vat_ph_re.match(vat)))


def check_vat_ru(self, vat):
    """Check Russia VAT number.

    Method copied from vatnumber 1.2 lib
    https://code.google.com/archive/p/vatnumber/
    """
    if len(vat) != 10 and len(vat) != 12:
        return False
    try:
        int(vat)
    except ValueError:
        return False

    if len(vat) == 10:
        check_sum = 2 * int(vat[0]) + 4 * int(vat[1]) + 10 * int(vat[2]) + \
            3 * int(vat[3]) + 5 * int(vat[4]) + 9 * int(vat[5]) + \
            4 * int(vat[6]) + 6 * int(vat[7]) + 8 * int(vat[8])
        check = check_sum % 11
        if check % 10 != int(vat[9]):
            return False
    else:
        check_sum1 = 7 * int(vat[0]) + 2 * int(vat[1]) + 4 * int(vat[2]) + \
            10 * int(vat[3]) + 3 * int(vat[4]) + 5 * int(vat[5]) + \
            9 * int(vat[6]) + 4 * int(vat[7]) + 6 * int(vat[8]) + \
            8 * int(vat[9])
        check = check_sum1 % 11

        if check != int(vat[10]):
            return False
        check_sum2 = 3 * int(vat[0]) + 7 * int(vat[1]) + 2 * int(vat[2]) + \
            4 * int(vat[3]) + 10 * int(vat[4]) + 3 * int(vat[5]) + \
            5 * int(vat[6]) + 9 * int(vat[7]) + 4 * int(vat[8]) + \
            6 * int(vat[9]) + 8 * int(vat[10])
        check = check_sum2 % 11
        if check != int(vat[11]):
            return False
    return True


def check_vat_rs(self, vat):
    """VAT validation in Serbia."""
    vat = vat.removeprefix('RS')
    return stdnum.util.get_cc_module('rs', 'vat').is_valid(vat)


def check_vat_tr(self, vat):
    """VAT validation in Turkey."""
    return (stdnum.util.get_cc_module('tr', 'tckimlik').is_valid(vat)
            or stdnum.util.get_cc_module('tr', 'vkn').is_valid(vat))


def check_vat_sa(self, vat):
    """Check company VAT TIN according to ZATCA specifications: The VAT number
    should start and begin with a '3' and be 15 digits long

    Saudi Arabia TIN validation.
    """
    return _check_vat_sa_re.match(vat) or False


def check_vat_ua(self, vat):
    """≙ ``check_vat_ua`` (``odoo19c: :657-658``)."""
    return len(vat[2:] if vat.startswith('UA') else vat) in {8, 10, 12}


def check_vat_uy(self, vat):
    """Taken from python-stdnum's master branch, as the release doesn't handle
    RUT numbers starting with 22.
    origin https://github.com/arthurdejong/python-stdnum/blob/master/stdnum/uy/rut.py
    FIXME Can be removed when python-stdnum does a new release.
    """
    def compact(number):
        """Convert the number to its minimal representation."""
        number = clean(number, ' -').upper().strip()
        if number.startswith('UY'):
            return number[2:]
        return number

    def calc_check_digit(number):
        """Calculate the check digit."""
        weights = (4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
        total = sum(int(n) * w for w, n in zip(weights, number))
        return str(-total % 11)

    vat = compact(vat)

    return (
        vat.isdigit()               # InvalidFormat
        and len(vat) == 12          # InvalidLength
        and '01' <= vat[:2] <= '22'  # InvalidComponent
        and vat[2:8] != '000000'
        and vat[8:11] == '001'
        and vat[-1] == calc_check_digit(vat)  # Invalid Check Digit
    )


def check_vat_uz(self, vat):
    """≙ ``check_vat_uz`` (``odoo19c: :689-690``)."""
    return len(vat) == 9 and vat.isdigit()


def check_vat_ve(self, vat):
    """Venezuela VAT validation.

    https://tin-check.com/en/venezuela/ — sources last visited on 2022-12-09.
    VAT format: (kind - 1 letter)(identifier number - 8-digit number)(check
    digit - 1 digit).
    """
    vat_regex = re.compile(r"""
        ([vecjpg])                          # group 1 - kind
        (
            (?P<optional_1>-)?                      # optional '-' (1)
            [0-9]{2}
            (?(optional_1)(?P<optional_2>[.])?)     # optional '.' (2) only if (1)
            [0-9]{3}
            (?(optional_2)[.])                      # mandatory '.' if (2)
            [0-9]{3}
            (?(optional_1)-)                        # mandatory '-' if (1)
        )                                   # group 2 - identifier number
        ([0-9]{1})                          # group X - check digit
    """, re.VERBOSE | re.IGNORECASE)

    matches = re.fullmatch(vat_regex, vat)
    if not matches:
        return False

    kind, identifier_number, *_rest, check_digit = matches.groups()
    kind = kind.lower()
    identifier_number = identifier_number.replace("-", "").replace(".", "")
    check_digit = int(check_digit)

    if kind == 'v':                   # Venezuela citizenship
        kind_digit = 1
    elif kind == 'e':                 # Foreigner
        kind_digit = 2
    elif kind == 'c' or kind == 'j':  # Township/Communal Council or Legal entity
        kind_digit = 3
    elif kind == 'p':                 # Passport
        kind_digit = 4
    else:                             # Government ('g')
        kind_digit = 5

    # === Checksum validation ===
    multipliers = [3, 2, 7, 6, 5, 4, 3, 2]
    checksum = kind_digit * 4
    checksum += sum(int(n) * m for n, m in zip(identifier_number, multipliers))

    checksum_digit = 11 - checksum % 11
    if checksum_digit > 9:
        checksum_digit = 0

    return check_digit == checksum_digit


def check_vat_in(self, vat):
    """reference from https://www.gstzen.in/a/format-of-a-gst-number-gstin.html"""
    if vat and len(vat) == 15:
        all_gstin_re = [
            r'[0-9]{2}[a-zA-Z]{5}[0-9]{4}[a-zA-Z]{1}[1-9A-Za-z]{1}[Zz1-9A-Ja-j]{1}[0-9a-zA-Z]{1}',  # Normal, Composite, Casual GSTIN
            r'[0-9]{4}[A-Z]{3}[0-9]{5}[UO]{1}[N][A-Z0-9]{1}',  # UN/ON Body GSTIN
            r'[0-9]{4}[A-Z]{3}[0-9]{5}[A-Z]{3}',  # Revised NRI GSTIN
            r'[0-9]{4}[a-zA-Z]{3}[0-9]{5}[N][R][0-9a-zA-Z]{1}',  # NRI GSTIN
            r'[0-9]{2}[a-zA-Z]{4}[a-zA-Z0-9]{1}[0-9]{4}[a-zA-Z]{1}[1-9A-Za-z]{1}[DK]{1}[0-9a-zA-Z]{1}',  # TDS GSTIN
            r'[0-9]{2}[a-zA-Z]{5}[0-9]{4}[a-zA-Z]{1}[1-9A-Za-z]{1}[C]{1}[0-9a-zA-Z]{1}',  # TCS GSTIN
        ]
        return any(re.compile(rx).match(vat) for rx in all_gstin_re)
    return False


def check_vat_br(self, vat):
    """≙ ``check_vat_br`` (``odoo19c: :761-777``) — CPF por ``stdnum``, CNPJ propio."""
    def is_cnpj_valid(number):
        number = clean(number, ' -./').strip().upper()
        if number.startswith('000000000000') or len(number) != 14:
            return False
        if _check_vat_br_re.match(number):
            values = [ord(n) - 48 for n in number[:12]]
            weights = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
            d1 = (11 - sum(w * v for w, v in zip(weights, values))) % 11 % 10
            values.append(d1)
            weights = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
            d2 = (11 - sum(w * v for w, v in zip(weights, values))) % 11 % 10
            return number[-2:] == f'{d1}{d2}'
        return False

    is_cpf_valid = stdnum.get_cc_module('br', 'cpf').is_valid
    return is_cpf_valid(vat) or is_cnpj_valid(vat)


def check_vat_cr(self, vat):
    """≙ ``check_vat_cr`` (``odoo19c: :781-787``).

    CÉDULA FÍSICA: 9 digits · CÉDULA JURÍDICA: 10 digits ·
    CÉDULA DIMEX: 11 or 12 digits · CÉDULA NITE: 10 digits
    """
    return _check_vat_cr_re.match(vat) or False


def check_vat_vn(self, vat):
    """VAT format validator for Vietnam.

    Supported formats:
    - 10-digit format (Enterprise tax ID): e.g., 0101243150
    - 13-digit format with branch suffix: e.g., 0101243150-001
    - 12-digit format (Personal ID / Citizen ID - CCCD): e.g., 079123456789
      (used as tax ID for individuals from July 1st, 2025)

    Note:
    - stdnum.vn.mst.validate() currently only supports 10- and 13-digit VAT numbers
    - and does not accept the 12-digit personal tax ID (CCCD) format introduced
      from 01/07/2025.
    - This helper provides a lightweight format-level validator for use in the meantime.
    - Can be removed once stdnum.vn.mst adds CCCD support.
    """
    vat = vat.strip()
    return bool(_check_vat_vn_re.match(vat))


def check_vat_id(self, vat):
    """Temporary Indonesian VAT validation to support the new format
    introduced in January 2024."""
    vat = clean(vat, ' -.').strip()

    if len(vat) not in (15, 16) or not vat.isdecimal():
        return False

    # VAT could be 15 (old numbers) or 16 digits. If there are 15 digits long,
    # the 10th digit is a luhn checksum. In some cases, the 15 digits can be
    # transformed in a 16-digit by adding a 0 in front. In such case, we can
    # verify the luhn checksum like for the 15 digits by removing the 0.
    # However, for newly created VAT 16-digits VAT number, there is no checksum.
    if len(vat) == 16 and vat[0] != '0':
        return True

    try:
        luhn.validate(vat[0:9] if len(vat) == 15 else vat[1:10])
    except (InvalidFormat, InvalidChecksum):
        return False

    return True


def check_vat_th(self, vat):
    """≙ ``check_vat_th`` (``odoo19c: :884-886``)."""
    check_func = stdnum.util.get_cc_module('th', 'tin').is_valid
    return check_func(vat)


def check_vat_de(self, vat):
    """≙ ``check_vat_de`` (``odoo19c: :888-891``)."""
    is_valid_vat = stdnum.util.get_cc_module("de", "vat").is_valid
    is_valid_stnr = stdnum.util.get_cc_module("de", "stnr").is_valid
    return is_valid_vat(vat) or is_valid_stnr(vat)


def check_vat_il(self, vat):
    """≙ ``check_vat_il`` (``odoo19c: :893-895``)."""
    check_func = stdnum.util.get_cc_module('il', 'idnr').is_valid
    return check_func(vat)


def check_vat_ma(self, vat):
    """≙ ``check_vat_ma`` (``odoo19c: :897-898``)."""
    return vat.isdigit() and len(vat) == 8


def check_vat_tw(self, vat):
    """Since Feb. 2025, due to the imminent exhaustion of the UBN numbers, the
    validation logic was changed from using a division by 10 for the final
    check to using a division by 5, making numbers that were previously invalid
    now valid.

    The stdnum implementation of the VAT validation is not up to date with this
    latest update, so we implement our own validation to support these new
    valid UBNs.
    """
    vat = stdnum.util.get_cc_module("tw", "vat").compact(vat)
    if len(vat) != 8 or not vat.isdigit():
        return False  # The length is fixed, and we will expect it to be 8.

    logic_multiplier = [1, 2, 1, 2, 1, 2, 4, 1]  # set by the official logic
    # Multiply each of the 8 digits of the VAT number by the corresponding
    # digit of the logic multiplier. For a two-digit product like 20, you would
    # add its digits (2 + 0) to the total sum, so we convert the sums here to
    # strings in order to make it easier later on.
    products = [str(a * int(b)) for a, b in zip(logic_multiplier, vat)]
    if vat[6] != '7':
        # If the 7th number is not 7, we simply sum everything and check that
        # the result is divisible by 5.
        checksum = sum(int(d) for d in ''.join(products))
        return checksum % 5 == 0
    # If the 7th number is 7, we calculate two sums:
    # z1: the total sum where the 7th position's contribution is taken as 1.
    # z2: the total sum where the 7th position's contribution is taken as 0.
    # The VAT number is valid if either Z1 or Z2 (or both) is divisible by 5.
    base_checksum = sum(int(d) for d in "".join(products[0:6] + products[7:]))
    return (base_checksum + 1) % 5 == 0 or base_checksum % 5 == 0


# === Los ocho formateadores ===============================================

def format_vat_al(self, vat):
    """≙ ``format_vat_al`` (``odoo19c: :810-814``)."""
    vat_prefix, vat_number = self._split_vat(vat)
    stdnum_vat_format = stdnum.util.get_cc_module('al', 'nipt').compact
    vat_number = stdnum_vat_format(vat_number)
    return f'{vat_prefix}{vat_number}'


def format_vat_eu(self, vat):
    """Foreign companies that trade with non-enterprises in the EU may have a
    VATIN starting with "EU" instead of a country code."""
    return vat


def format_vat_ch(self, vat):
    """≙ ``format_vat_ch`` (``odoo19c: :821-823``)."""
    stdnum_vat_format = stdnum.util.get_cc_module('ch', 'vat').format
    return stdnum_vat_format('CH' + vat)[2:]


def format_vat_cl(self, vat):
    """It is better to always have the -"""
    vat = vat.replace('.', '').replace('CL', '').replace(' ', '')
    vat = vat.replace('-', '').upper()
    if len(vat) > 2:
        return vat[:-1] + '-' + vat[-1]
    return vat


def format_vat_co(self, vat):
    """It is better to always have the -"""
    stdnum_vat_format = stdnum.util.get_cc_module('co', 'vat').format
    vat = stdnum_vat_format(vat).replace('.', '').replace('-', '')
    if len(vat) > 2:
        return vat[:-1] + '-' + vat[-1]
    return vat


def format_vat_vn(self, vat):
    """It is better to always have the -"""
    stdnum_vat_format = stdnum.util.get_cc_module('vn', 'vat').format
    if _check_vat_vn_companies_re.match(vat):
        return stdnum_vat_format(vat)
    return vat


def format_vat_hu(self, vat):
    """We put the - back as we require it for the EDI and the different parts
    will make it clear to the user"""
    stdnum_vat_fix_func = stdnum.util.get_cc_module('hu', 'vat').compact
    vat = stdnum_vat_fix_func(vat)
    if _check_tin_hu_companies_re.match(vat):
        vat = vat[:8] + '-' + vat[8] + '-' + vat[9] + vat[10]
    return vat


def format_vat_is(self, vat):
    """≙ ``format_vat_is`` (``odoo19c: :856-860``)."""
    vat_prefix, vat_number = self._split_vat(vat)
    stdnum_vat_format = stdnum.util.get_cc_module('is_', 'vsk').compact
    vat_number = stdnum_vat_format(vat_number)
    return f'{vat_prefix}{vat_number}'


def format_vat_sm(self, vat):
    """≙ ``format_vat_sm`` (``odoo19c: :900-902``)."""
    stdnum_vat_format = stdnum.util.get_cc_module('sm', 'vat').compact
    return stdnum_vat_format('SM' + vat)[2:]


def _convert_hu_local_to_eu_vat(self, local_vat):
    """≙ ``_convert_hu_local_to_eu_vat`` (``odoo19c: :947-950``)."""
    if (_check_tin_hu_companies_re.match(local_vat)
            or _check_tin_hu_european_re.match(local_vat)):
        return f'HU{local_vat[:8]}'
    return False


# === Los tres enganches de escritura ======================================

def save(self, previous, *args, **kwargs):
    """≙ ``create`` (``odoo19c: :963-967``) **y** ``write`` (``:969-974``).

    **Divergencia de mecanismo, declarada — no de alcance.** La fuente engancha
    dos métodos porque su ORM tiene dos entradas de mutación; aquí la entrada
    es una sola, ``Model.save``, y el par ``crear`` / ``escribir`` se distingue
    por ``self._state.adding``. El comportamiento portado es el mismo, símbolo
    a símbolo:

    - **crear** — la fuente saca ``vies_valid`` de la cola de recomputación
      **siempre** tras crear, para que el valor que vino en el ``vals`` no se
      pise con el ``compute``.
    - **escribir** — lo saca **sólo** cuando el cambio viene de una
      importación (``self.env.context.get('import_file')``).

    Por qué no se enganchan ``create``/``write`` como allá, medido:
    ``grep -cE "^    def (create|write)\\(" src/addons/base/models/res_partner.py``
    da **0** — ``ResPartner`` no declara ninguno de los dos, y ``wrap_method``
    exige implementación previa (``src/orm/method_chain.py:246-250``).
    Declararlos aquí, sobre un modelo de ``base``, sería el defecto de sitio de
    :ref:`h-api-568`. Su porte sobre ``res.partner`` es la tarea **#463**;
    cuando exista, este enganche se reparte en los dos sin cambiar conducta.
    """
    creating = self._state.adding
    result = previous(*args, **kwargs)
    if creating or get_context().get('import_file'):
        _forget_vies_recompute(type(self), [self.pk])
    return result


def _create_contact_parent_company(self, previous):
    """≙ ``_create_contact_parent_company`` (``odoo19c: :976-981``)."""
    new_company = previous()
    if new_company and self.vies_valid:
        _forget_vies_recompute(type(new_company), [new_company.pk])
        new_company.vies_valid = self.vies_valid
        new_company.save(update_fields=['vies_valid'])
    return new_company


def _forget_vies_recompute(model, record_ids):
    """≙ ``env.remove_to_compute(self._fields['vies_valid'], …)``."""
    field = model._meta.get_field('vies_valid')
    env().remove_to_compute(field, record_ids)


# === El enganche ==========================================================

def apply_base_vat_extensions():
    """Cuelga sobre ``res.partner`` lo que ``base_vat`` le declara — ≙ ``_inherit``."""
    extend_model('base', 'ResPartner', campos={
        'vies_valid': fields.Boolean(
            default=False, verbose_name='Intra-Community Valid',
            help_text='European VAT numbers are automatically checked on the '
                      'VIES database (Odoo vies_valid).'),
    }, propiedades={
        'perform_vies_validation': _compute_perform_vies_validation,
    }, metodos={
        '_run_vat_checks': _run_vat_checks,
        '_inverse_vat': _inverse_vat,
        '_onchange_vat': _onchange_vat,
        '_get_country_specific_vat_variants': _get_country_specific_vat_variants,
        '_compute_perform_vies_validation': _compute_perform_vies_validation,
        '_compute_vies_valid': _compute_vies_valid,
        '_split_vat': _split_vat,
        '_get_iap_vies_credentials': _get_iap_vies_credentials,
        '_get_iap_vies_endpoint': _get_iap_vies_endpoint,
        '_check_vies_iap': _check_vies_iap,
        '_cron_check_vies_iap': _cron_check_vies_iap,
        '_check_vies_update_iap': _check_vies_update_iap,
        '_update_vies_status': _update_vies_status,
        '_check_vat_number': _check_vat_number,
        '_build_vat_error_message': _build_vat_error_message,
        '_format_vat_number': _format_vat_number,
        '_convert_hu_local_to_eu_vat': _convert_hu_local_to_eu_vat,
        '_get_vat_required_valid': _get_vat_required_valid,
        '_ie_check_char': _ie_check_char,
        'is_valid_ruc_ec': is_valid_ruc_ec,
        'check_vat_al': check_vat_al,
        'check_vat_jp': check_vat_jp,
        'check_vat_do': check_vat_do,
        'check_vat_ro': check_vat_ro,
        'check_vat_gr': check_vat_gr,
        'check_vat_gt': check_vat_gt,
        'check_vat_hu': check_vat_hu,
        'check_vat_ch': check_vat_ch,
        'check_vat_ec': check_vat_ec,
        'check_vat_ie': check_vat_ie,
        'check_vat_mx': check_vat_mx,
        'check_vat_no': check_vat_no,
        'check_vat_pe': check_vat_pe,
        'check_vat_ph': check_vat_ph,
        'check_vat_ru': check_vat_ru,
        'check_vat_rs': check_vat_rs,
        'check_vat_tr': check_vat_tr,
        'check_vat_sa': check_vat_sa,
        'check_vat_ua': check_vat_ua,
        'check_vat_uy': check_vat_uy,
        'check_vat_uz': check_vat_uz,
        'check_vat_ve': check_vat_ve,
        'check_vat_in': check_vat_in,
        'check_vat_br': check_vat_br,
        'check_vat_cr': check_vat_cr,
        'check_vat_vn': check_vat_vn,
        'check_vat_id': check_vat_id,
        'check_vat_th': check_vat_th,
        'check_vat_de': check_vat_de,
        'check_vat_il': check_vat_il,
        'check_vat_ma': check_vat_ma,
        'check_vat_tw': check_vat_tw,
        'format_vat_al': format_vat_al,
        'format_vat_eu': format_vat_eu,
        'format_vat_ch': format_vat_ch,
        'format_vat_cl': format_vat_cl,
        'format_vat_co': format_vat_co,
        'format_vat_vn': format_vat_vn,
        'format_vat_hu': format_vat_hu,
        'format_vat_is': format_vat_is,
        'format_vat_sm': format_vat_sm,
    }, overrides={
        'save': save,
        '_create_contact_parent_company': _create_contact_parent_company,
    }, luego=_hang_precompiled_regexes)


def _hang_precompiled_regexes(model):
    """Cuelga las quince expresiones regulares como atributos de clase.

    La fuente las declara **dentro** de la clase (``:385``…``:790``) y sus
    métodos las leen con ``self._check_vat_ch_re``. Colgarlas conserva ese
    acceso, que es parte del contrato: una localización que herede del partner
    puede redefinir una sin tocar el método que la usa.
    """
    for name, value in (
        ('_check_vat_al_re', _check_vat_al_re),
        ('_check_tin1_ro_natural_persons', _check_tin1_ro_natural_persons),
        ('_check_tin2_ro_natural_persons', _check_tin2_ro_natural_persons),
        ('_check_vat_gt_testing_infile', _check_vat_gt_testing_infile),
        ('_check_tin_hu_individual_re', _check_tin_hu_individual_re),
        ('_check_tin_hu_companies_re', _check_tin_hu_companies_re),
        ('_check_tin_hu_european_re', _check_tin_hu_european_re),
        ('_check_vat_ch_re', _check_vat_ch_re),
        ('_check_vat_mx_re', _check_vat_mx_re),
        ('_check_vat_ph_re', _check_vat_ph_re),
        ('_check_vat_sa_re', _check_vat_sa_re),
        ('_check_vat_br_re', _check_vat_br_re),
        ('_check_vat_cr_re', _check_vat_cr_re),
        ('_check_vat_vn_re', _check_vat_vn_re),
        ('_check_vat_vn_companies_re', _check_vat_vn_companies_re),
    ):
        if not hasattr(model, name):
            setattr(model, name, value)

    #: ≙ el ``inverse="_inverse_vat"`` de la fuente (``:104``) en su única
    #: forma disponible aquí: el validador de campo de Django. Ver la
    #: divergencia 2 del encabezado y la tarea **#462**.
    vat_field = model._meta.get_field('vat')
    if validate_rfc not in vat_field.validators:
        vat_field.validators.append(validate_rfc)
