r"""``account.edi.common`` — la base compartida por todos los constructores UBL/CII.

Adaptación de ``odoo19c: addons/account_edi_ubl_cii/models/account_edi_common.py``
(``odoo-tools@622ddc2a``, LGPL-3, 1148 líneas) — atribución y aviso de licencia
preservados (DEC-KX-03).

Cobertura: 45 de 45 símbolos presentes
=======================================

``FloatFmt`` 4/4 portados · ``AccountEdiCommon`` **41/41 presentes**, de los
cuales **20 portados** y **21 bloqueados por pieza nombrada** (cada uno lo dice
en su propio docstring y llama a :func:`_blocked`, que levanta ``UserError``
nombrando la pieza — nunca falla en silencio).

Los 20 portados: ``_vals_to_etree`` ``_etree_to_string`` ``_define_document_type``
``_get_document_type`` ``_is_document`` ``format_float``
``_get_currency_decimal_places`` ``_find_value`` ``_can_export_selfbilling``
``_get_tax_category_code`` ``_get_tax_exemption_reason``
``_check_required_fields`` ``_import_currency`` ``_import_description``
``_import_prepaid_amount`` ``_retrieve_rebate_val``
``_retrieve_charge_allowance_vals`` ``_get_document_allowance_charge_xpaths``
``_get_invoice_line_xpaths`` ``_correct_invoice_tax_amount``.

**Un símbolo NUEVO, declarado como tal:** ``_field_label`` — no tiene
contraparte en la referencia. Ahí la etiqueta legible de un campo sale de una
sola llamada al ORM (``record.fields_get(names)``); aquí se lee de ``Meta``, y
esa lectura se aísla en su propio método para no ensuciar
``_check_required_fields``. Total de la clase: 42 = 41 + 1.

**Bloqueo que se propaga, y se declara:** ``_get_tax_exemption_reason``
(portado) llama a ``_get_belgian_cocontractant_note`` (bloqueado) en su primera
rama, la de impuesto con importe cero. Es decir: el símbolo está portado y su
rama belga levanta con la causa nombrada. No se silencia devolviendo ``''``,
que convertiría un bloqueo en un dato falso.

Cuatro funciones de módulo, todas del porte y ninguna de la referencia:
:func:`_blocked`, :func:`_float_repr`, :func:`_find_xml_value` y
:func:`_format_lang_amount` — las tres últimas sustituyen imports ausentes
(ver la tabla de sustituciones abajo).

Clase Python, no ``AbstractModel`` — la convención del árbol
==============================================================

La referencia declara ``models.AbstractModel`` con ``_name`` propio. Aquí el
hogar de un mixin de comportamiento es una **clase Python plana** que preserva
``_name``/``_description`` como atributos de clase — mismo criterio que
``account/models/account_move_send.py``, ``account_document_import_mixin.py``
y ``product_catalog_mixin.py`` ya fijaron en este árbol.

Dos consecuencias que se declaran una vez para toda la familia:

1. **Todos los métodos son ``@classmethod``.** En la referencia son métodos de
   un ``AbstractModel``, que se invoca a nivel de modelo (``self`` es el
   recordset vacío del propio mixin, no un registro). El ``@classmethod`` es
   su forma exacta aquí, y hace que cada ``cls.X(...)`` apunte a un
   ``@classmethod`` por construcción. Los dos ``@api.model`` de la fuente
   (``_retrieve_rebate_val``, ``_retrieve_charge_allowance_vals``) se retiran:
   ``@api.model`` significa "a nivel de modelo", que es justo lo que
   ``@classmethod`` ya declara.
2. **``_inherit`` se materializa como herencia de Python.** El MRO de C3 hace
   lo que hace ``_inherit`` —incluida la forma de lista, cuyo orden se
   preserva en el orden de las bases— y ``super()`` sigue funcionando dentro
   de un ``@classmethod``. El atributo ``_inherit`` se conserva verbatim en
   cada subclase (``atributos-de-clase-de-modelo.md``).

La puerta está bloqueada, las habitaciones no — y por qué
==========================================================

Los constructores de esta familia trabajan casi enteramente sobre **dicts**
(``vals``, ``document_node``, ``base_line``): son transformaciones puras y se
portan verbatim. Lo que sí toca registros son las **puertas de entrada** —
``_export_invoice``/``_init_invoice_export_values`` del lado de exportación y
``_import_invoice_ubl_cii``/``_ubl_import_invoice`` del lado de importación—,
y ésas están bloqueadas por piezas medidas ausentes:

.. list-table:: Piezas ausentes, medidas antes de escribir (``grep -rn … addons/ src/``)
   :header-rows: 1
   :widths: 45 12 43

   * - Pieza que la referencia usa
     - Hits
     - Dónde debería estar
   * - ``_prepare_base_line_for_taxes_computation``
     - **0**
     - ``account/models/account_tax.py`` — su propio docstring (``:82-90``)
       declara que **la envoltura de base-lines no se porta**
   * - ``_add_tax_details_in_base_lines`` / ``_round_base_lines_tax_details``
     - **0**
     - ídem
   * - ``_aggregate_base_lines_tax_details``
     - **0**
     - ídem
   * - ``AccountMove.invoice_line_ids``
     - **0**
     - ``account/models/account_move.py`` — el modelo declara 11 campos
       (``name ref date state payment_state move_type journal partner currency
       company amount_total``); la mitad *factura* no está portada
   * - ``_get_edi_creation``
     - **0**
     - ``AccountMove`` — contexto de edición diferida del importador
   * - ``_retrieve_partner`` / ``_retrieve_product``
     - **0**
     - ``ResPartner`` / ``ProductProduct``
   * - ``_run_vat_checks`` / ``_find_or_create_bank_account``
     - **0**
     - ``ResPartner`` / ``ResPartnerBank``
   * - ``_check_company_domain`` / ``_get_line_vals_list``
     - **0**
     - ``AccountJournal`` / ``AccountMove``
   * - ``_validate_repartition_lines``
     - **0**
     - ``AccountTax``
   * - ``get_external_id`` / ``env.ref`` (registro de xmlid)
     - **0**
     - GAP ya declarado por varios archivos de ``account``
   * - ``message_post`` sobre ``account.move``
     - n/a
     - existe en ``addons/mail/models/mail_thread.py:88``, pero
       ``AccountMove`` no hereda ``MailThread`` en este árbol

Ninguna de esas piezas vive en el write-set de este pase
(``addons/account_edi_ubl_cii/``): construirlas es tocar ``addons/account``,
``addons/product`` y ``src/addons/base``. Desenlace declarado: **bloqueado por
piezas nombradas fuera del alcance de escritura**, con sucesor = portar la
mitad *factura* de ``account.move`` + la envoltura de base-lines de
``account.tax``. Es el mismo desenlace, y por la misma razón, que
``account/models/account_move_send.py`` ya registró para 36 de sus 50
símbolos.

Sustituciones del árbol (medidas con ``grep -ic … uv.lock``)
==============================================================

.. list-table::
   :header-rows: 1
   :widths: 30 12 58

   * - Import de la fuente
     - Medido
     - Qué se usa aquí
   * - ``lxml``
     - **76**
     - se usa tal cual — es dependencia declarada
   * - ``markupsafe.Markup``
     - **0**
     - no se importa; su único consumidor
       (``_log_import_invoice_ubl_cii``) está bloqueado por
       ``message_post``
   * - ``odoo.tools.float_repr``
     - ausente
     - vendorizado como :func:`_float_repr` (dos líneas; ``src/tools/
       float_utils.py:10`` declara explícitamente que lo deja fuera)
   * - ``odoo.tools.misc.formatLang``
     - ausente
     - f-string con el símbolo de la divisa — misma divergencia que
       ``account/models/account_payment_term.py`` ya declaró
   * - ``odoo.tools.xml_utils.find_xml_value``
     - ausente
     - vendorizado como :func:`_find_xml_value` (tres líneas, verbatim)
   * - ``odoo.tools.translate._lt``
     - ausente
     - ``tools.translate._`` **ya es perezoso** en este árbol (devuelve
       ``_lazy_translate(...)``), así que es el equivalente exacto de ``_lt``
   * - ``clean_context`` / ``sanitize_account_number``
     - —
     - la fuente los importa y **no los usa** (medido: 1 hit cada uno, la
       propia línea de import). No se importan aquí.
   * - ``datetime`` · ``float_compare`` · ``float_is_zero`` · ``html2plaintext``
     - —
     - sí existen en el árbol, pero sus únicos consumidores
       (``_retrieve_invoice_line_vals``, ``_retrieve_line_vals``,
       ``_get_belgian_cocontractant_note``) están bloqueados. Se re-importan
       el día que se desbloqueen.

El acceso ``env`` — mecanismo construido, con sus límites declarados
=====================================================================

La referencia usa ``self.env['<modelo>']`` para llegar al registro de modelos.
Este árbol ya tiene la pieza equivalente —``orm.registry.model_by_name``, que
resuelve un ``_name`` de la referencia a su clase Django— y el traductor de
dominios ``orm.domains.to_q``. :data:`env` los compone en el acceso mínimo que
esta familia necesita (``porte-completo-no-parcial.md``: si el stack no trae el
mecanismo, se construye con la API pública, que aquí es el ``QuerySet``).

**Lo que NO emula, y por tanto se declara:** aritmética de recordsets
(``+``/``|``/``+=``), ``.ids``, ``.sudo()``, ``.with_company()``,
``.with_context()``, ``.browse()`` sobre varios ids, ``.new()``. Todo método
de la fuente que las necesite está bloqueado por otra razón ya listada arriba;
si alguno llegase aquí, ``__getattr__`` delega en la clase Django y falla
ruidoso con el nombre del atributo, nunca en silencio.
"""
from lxml import etree

from addons.account.tools import dict_to_xml
from exceptions import UserError
from orm.domains import to_q
from orm.environments import get_context, get_current_company
from orm.registry import model_by_name
from tools.float_utils import float_round
from tools.misc import html_escape
from tools.translate import _


def _blocked(symbol, missing):
    """Levanta nombrando el símbolo y la pieza que lo bloquea.

    Mismo mecanismo que ``account/models/account_move_send.py::_blocked``: un
    símbolo bloqueado **existe** con su firma (el porte es completo en
    presencia) y falla ruidoso al invocarse, con la causa greppeable. Nunca
    devuelve ``None`` en silencio, que es lo que convertiría un bloqueo en un
    dato falso.
    """
    raise UserError(
        f'{symbol}: bloqueado — {missing} (ver la tabla de piezas ausentes en '
        f'el docstring de account_edi_common.py).')


def _float_repr(value, precision_digits):
    """≙ ``odoo.tools.float_utils.float_repr`` — vendorizado.

    ``src/tools/float_utils.py:10`` declara que lo deja fuera del porte. Son
    dos líneas y esta familia lo necesita en ``FloatFmt.__str__`` y en
    ``format_float``; el sitio correcto para un segundo consumidor sería
    ``src/tools/float_utils.py``, fuera del write-set de este pase.
    """
    return '%.*f' % (precision_digits, value)


def _find_xml_value(xpath, xml_element, namespaces=None):
    """≙ ``odoo.tools.xml_utils.find_xml_value`` (``odoo19c: :339-341``).

    Vendorizado verbatim: ``src/tools/`` no tiene ``xml_utils`` y crearlo cae
    fuera del write-set de este pase (mismo criterio, y mismo precedente, que
    ``account/tools/dict_to_xml.py`` con ``remove_control_characters``).
    """
    element = xml_element.xpath(xpath, namespaces=namespaces)
    return element[0].text if element else None


def _format_lang_amount(amount, currency):
    """Sustituto declarado de ``odoo.tools.misc.formatLang``.

    ``formatLang`` formatea por *locale* (separadores, posición del símbolo)
    leyendo el idioma del entorno. Este árbol no lo porta —divergencia ya
    declarada por ``account/models/account_payment_term.py`` y
    ``accrued_orders.py``— así que se compone el texto con el número redondeado
    a los decimales de la divisa y su símbolo.
    """
    places = getattr(currency, 'decimal_places', 2)
    symbol = getattr(currency, 'symbol', '') or getattr(currency, 'name', '')
    return f'{_float_repr(float_round(amount, places), places)} {symbol}'.strip()


class _ModelProxy:
    """≙ el recordset vacío que devuelve ``self.env['<modelo>']``.

    Expone las tres operaciones que esta familia usa sobre él —``search``,
    ``browse``, ``create``— traducidas a la API pública de Django, y delega
    todo lo demás en la clase del modelo (donde viven los ``@classmethod``
    portados). Ver "El acceso ``env``" en el docstring del módulo para lo que
    deliberadamente NO emula.
    """

    __slots__ = ('_model',)

    def __init__(self, model):
        self._model = model

    def __getattr__(self, name):
        return getattr(self._model, name)

    def __bool__(self):
        """El recordset vacío de la referencia es falso — ``if not partner``."""
        return False

    def __len__(self):
        return 0

    def search(self, domain, limit=None, order=None):
        """≙ ``search`` — el dominio se traduce con ``orm.domains.to_q``."""
        queryset = self._model.objects.filter(to_q(domain, self._model))
        if order:
            queryset = queryset.order_by(*[o.strip() for o in order.split(',')])
        if limit == 1:
            return queryset.first()
        return list(queryset[:limit] if limit else queryset)

    def browse(self, ids):
        """≙ ``browse`` para un único id — la forma que esta familia usa."""
        if isinstance(ids, (list, tuple, set)):
            return list(self._model.objects.filter(pk__in=list(ids)))
        return self._model.objects.filter(pk=ids).first()

    def create(self, vals):
        """≙ ``create`` de un solo diccionario de valores."""
        return self._model.objects.create(**vals)


class _Env:
    """≙ ``self.env`` — el acceso al registro de modelos de la referencia."""

    def __getitem__(self, name):
        model = model_by_name(name)
        if model is None:
            raise UserError(
                _("El modelo '%s' no está cargado en este árbol.", name))
        return _ModelProxy(model)

    @staticmethod
    def _(source, *args, **kwargs):
        """≙ ``self.env._`` — el mismo traductor perezoso del árbol."""
        return _(source, *args, **kwargs)

    @property
    def company(self):
        """≙ ``self.env.company`` — la empresa activa del contexto."""
        return get_current_company()

    @property
    def context(self):
        """≙ ``self.env.context``."""
        return get_context()

    def ref(self, xmlid, raise_if_not_found=True):
        """≙ ``self.env.ref`` — **bloqueado**: no hay registro de xmlid.

        GAP ya medido y declarado por varios archivos de ``account``
        (``get_external_id``/``env.ref`` → 0 hits en el árbol).
        """
        if raise_if_not_found:
            _blocked('env.ref', 'no hay registro de xmlid (ir.model.data)')
        return None


#: La instancia única — sustituye a ``self.env`` en toda la familia.
env = _Env()

# -------------------------------------------------------------------------
# UNIT OF MEASURE
# -------------------------------------------------------------------------
UOM_TO_UNECE_CODE = {
    'uom.product_uom_unit': 'C62',
    'uom.product_uom_dozen': 'DZN',
    'uom.product_uom_kgm': 'KGM',
    'uom.product_uom_gram': 'GRM',
    'uom.product_uom_day': 'DAY',
    'uom.product_uom_hour': 'HUR',
    'uom.product_uom_minute': 'MIN',
    'uom.product_uom_ton': 'TNE',
    'uom.product_uom_meter': 'MTR',
    'uom.product_uom_km': 'KMT',
    'uom.product_uom_cm': 'CMT',
    'uom.product_uom_litre': 'LTR',
    'uom.product_uom_cubic_meter': 'MTQ',
    'uom.product_uom_lb': 'LBR',
    'uom.product_uom_oz': 'ONZ',
    'uom.product_uom_inch': 'INH',
    'uom.product_uom_foot': 'FOT',
    'uom.product_uom_mile': 'SMI',
    'uom.product_uom_floz': 'OZA',
    'uom.product_uom_qt': 'QTL',
    'uom.product_uom_gal': 'GLL',
    'uom.product_uom_cubic_inch': 'INQ',
    'uom.product_uom_cubic_foot': 'FTQ',
    'uom.product_uom_square_meter': 'MTK',
    'uom.product_uom_square_foot': 'FTK',
    'uom.product_uom_yard': 'YRD',
    'uom.product_uom_millimeter': 'MMT',
    'uom.product_uom_kwh': 'KWH',
}

# -------------------------------------------------------------------------
# ELECTRONIC ADDRESS SCHEME (EAS), see https://docs.peppol.eu/poacc/billing/3.0/codelist/eas/
# -------------------------------------------------------------------------
EAS_MAPPING = {
    'AD': {'9922': 'vat'},
    'AE': {'0235': 'vat'},
    'AL': {'9923': 'vat'},
    'AT': {'9915': 'vat'},
    'AU': {'0151': 'vat'},
    'BA': {'9924': 'vat'},
    'BE': {'0208': 'company_registry', '9925': 'vat'},
    'BG': {'9926': 'vat'},
    'CH': {'9927': 'vat', '0183': None},
    'CY': {'9928': 'vat'},
    'CZ': {'9929': 'vat'},
    'DE': {'9930': 'vat', '0246': 'l10n_de_widnr'},
    'DK': {'0184': 'vat', '0198': 'vat'},
    'EE': {'9931': 'vat'},
    'ES': {'9920': 'vat'},
    'FI': {'0216': None},
    'FR': {'0225': 'peppol_endpoint', '0009': 'company_registry', '9957': 'vat', '0002': None},  # `peppol_endpoint` used as place holder for custom logic via `_get_peppol_endpoint_value`
    'SG': {'0195': 'l10n_sg_unique_entity_number'},
    'GB': {'9932': 'vat'},
    'GR': {'9933': 'vat'},
    'HR': {'9934': 'vat', '0088': 'company_registry'},
    'HU': {'9910': 'l10n_hu_eu_vat'},
    'IE': {'9935': 'vat'},
    'IS': {'0196': 'vat'},
    'IT': {'0211': 'vat', '0210': 'l10n_it_codice_fiscale'},
    'JP': {'0221': 'vat'},
    'LI': {'9936': 'vat'},
    'LT': {'9937': 'vat'},
    'LU': {'9938': 'vat'},
    'LV': {'0218': 'company_registry', '9939': 'vat'},
    'MC': {'9940': 'vat'},
    'ME': {'9941': 'vat'},
    'MK': {'9942': 'vat'},
    'MT': {'9943': 'vat'},
    'MY': {'0230': None},
    # Do not add the vat for NL, since: "[NL-R-003] For suppliers in the Netherlands, the legal entity identifier
    # MUST be either a KVK or OIN number (schemeID 0106 or 0190)" in the Bis 3 rules (in PartyLegalEntity/CompanyID).
    'NG': {'0244': 'vat'},
    'NL': {'0106': None, '0190': None},
    'NO': {'0192': 'l10n_no_bronnoysund_number'},
    'NZ': {'0088': 'company_registry'},
    'PL': {'9945': 'vat'},
    'PT': {'9946': 'vat'},
    'RO': {'9947': 'vat'},
    'RS': {'9948': 'vat'},
    'SE': {'0007': 'company_registry', '9955': 'vat'},
    'SI': {'9949': 'vat'},
    'SK': {'9950': 'vat', '0245': 'company_registry'},
    'SM': {'9951': 'vat'},
    'TR': {'9952': 'vat'},
    'VA': {'9953': 'vat'},
    # DOM-TOM
    'BL': {'0009': 'siret', '9957': 'vat', '0002': None},  # Saint Barthélemy
    'GF': {'0009': 'siret', '9957': 'vat', '0002': None},  # French Guiana
    'GP': {'0009': 'siret', '9957': 'vat', '0002': None},  # Guadeloupe
    'MF': {'0009': 'siret', '9957': 'vat', '0002': None},  # Saint Martin
    'MQ': {'0009': 'siret', '9957': 'vat', '0002': None},  # Martinique
    'NC': {'0009': 'siret', '9957': 'vat', '0002': None},  # New Caledonia
    'PF': {'0009': 'siret', '9957': 'vat', '0002': None},  # French Polynesia
    'PM': {'0009': 'siret', '9957': 'vat', '0002': None},  # Saint Pierre and Miquelon
    'RE': {'0009': 'siret', '9957': 'vat', '0002': None},  # Réunion
    'TF': {'0009': 'siret', '9957': 'vat', '0002': None},  # French Southern and Antarctic Lands
    'WF': {'0009': 'siret', '9957': 'vat', '0002': None},  # Wallis and Futuna
    'YT': {'0009': 'siret', '9957': 'vat', '0002': None},  # Mayotte

    'AX': {'0216': None},  # Åland Islands
}

# -------------------------------------------------------------------------
# MAPPING FOR TAX EXEMPTION
# -------------------------------------------------------------------------
TAX_EXEMPTION_MAPPING = {
    'VATEX-EU-79-C': 'Exempt based on article 79, point c of Council Directive 2006/112/EC',
    'VATEX-EU-132': 'Exempt based on article 132 of Council Directive 2006/112/EC',
    'VATEX-EU-132-1A': 'Exempt based on article 132, section 1 (a) of Council Directive 2006/112/EC',
    'VATEX-EU-132-1B': 'Exempt based on article 132, section 1 (b) of Council Directive 2006/112/EC',
    'VATEX-EU-132-1C': 'Exempt based on article 132, section 1 (c) of Council Directive 2006/112/EC',
    'VATEX-EU-132-1D': 'Exempt based on article 132, section 1 (d) of Council Directive 2006/112/EC',
    'VATEX-EU-132-1E': 'Exempt based on article 132, section 1 (e) of Council Directive 2006/112/EC',
    'VATEX-EU-132-1F': 'Exempt based on article 132, section 1 (f) of Council Directive 2006/112/EC',
    'VATEX-EU-132-1G': 'Exempt based on article 132, section 1 (g) of Council Directive 2006/112/EC',
    'VATEX-EU-132-1H': 'Exempt based on article 132, section 1 (h) of Council Directive 2006/112/EC',
    'VATEX-EU-132-1I': 'Exempt based on article 132, section 1 (i) of Council Directive 2006/112/EC',
    'VATEX-EU-132-1J': 'Exempt based on article 132, section 1 (j) of Council Directive 2006/112/EC',
    'VATEX-EU-132-1K': 'Exempt based on article 132, section 1 (k) of Council Directive 2006/112/EC',
    'VATEX-EU-132-1L': 'Exempt based on article 132, section 1 (l) of Council Directive 2006/112/EC',
    'VATEX-EU-132-1M': 'Exempt based on article 132, section 1 (m) of Council Directive 2006/112/EC',
    'VATEX-EU-132-1N': 'Exempt based on article 132, section 1 (n) of Council Directive 2006/112/EC',
    'VATEX-EU-132-1O': 'Exempt based on article 132, section 1 (o) of Council Directive 2006/112/EC',
    'VATEX-EU-132-1P': 'Exempt based on article 132, section 1 (p) of Council Directive 2006/112/EC',
    'VATEX-EU-132-1Q': 'Exempt based on article 132, section 1 (q) of Council Directive 2006/112/EC',
    'VATEX-EU-135-1': 'Exempt based on article 135, section 1 of Council Directive 2006/112/EC',
    'VATEX-EU-143': 'Exempt based on article 143 of Council Directive 2006/112/EC',
    'VATEX-EU-143-1A': 'Exempt based on article 143, section 1 (a) of Council Directive 2006/112/EC',
    'VATEX-EU-143-1B': 'Exempt based on article 143, section 1 (b) of Council Directive 2006/112/EC',
    'VATEX-EU-143-1C': 'Exempt based on article 143, section 1 (c) of Council Directive 2006/112/EC',
    'VATEX-EU-143-1D': 'Exempt based on article 143, section 1 (d) of Council Directive 2006/112/EC',
    'VATEX-EU-143-1E': 'Exempt based on article 143, section 1 (e) of Council Directive 2006/112/EC',
    'VATEX-EU-143-1F': 'Exempt based on article 143, section 1 (f) of Council Directive 2006/112/EC',
    'VATEX-EU-143-1FA': 'Exempt based on article 143, section 1 (fa) of Council Directive 2006/112/EC',
    'VATEX-EU-143-1G': 'Exempt based on article 143, section 1 (g) of Council Directive 2006/112/EC',
    'VATEX-EU-143-1H': 'Exempt based on article 143, section 1 (h) of Council Directive 2006/112/EC',
    'VATEX-EU-143-1I': 'Exempt based on article 143, section 1 (i) of Council Directive 2006/112/EC',
    'VATEX-EU-143-1J': 'Exempt based on article 143, section 1 (j) of Council Directive 2006/112/EC',
    'VATEX-EU-143-1K': 'Exempt based on article 143, section 1 (k) of Council Directive 2006/112/EC',
    'VATEX-EU-143-1L': 'Exempt based on article 143, section 1 (l) of Council Directive 2006/112/EC',
    'VATEX-EU-144': 'Exempt based on article 144 of Council Directive 2006/112/EC',
    'VATEX-EU-146-1E': 'Exempt based on article 146 section 1 (e) of Council Directive 2006/112/EC',
    'VATEX-EU-148': 'Exempt based on article 148 of Council Directive 2006/112/EC',
    'VATEX-EU-148-A': 'Exempt based on article 148, section (a) of Council Directive 2006/112/EC',
    'VATEX-EU-148-B': 'Exempt based on article 148, section (b) of Council Directive 2006/112/EC',
    'VATEX-EU-148-C': 'Exempt based on article 148, section (c) of Council Directive 2006/112/EC',
    'VATEX-EU-148-D': 'Exempt based on article 148, section (d) of Council Directive 2006/112/EC',
    'VATEX-EU-148-E': 'Exempt based on article 148, section (e) of Council Directive 2006/112/EC',
    'VATEX-EU-148-F': 'Exempt based on article 148, section (f) of Council Directive 2006/112/EC',
    'VATEX-EU-148-G': 'Exempt based on article 148, section (g) of Council Directive 2006/112/EC',
    'VATEX-EU-151': 'Exempt based on article 151 of Council Directive 2006/112/EC',
    'VATEX-EU-151-1A': 'Exempt based on article 151, section 1 (a) of Council Directive 2006/112/EC',
    'VATEX-EU-151-1AA': 'Exempt based on article 151, section 1 (aa) of Council Directive 2006/112/EC',
    'VATEX-EU-151-1B': 'Exempt based on article 151, section 1 (b) of Council Directive 2006/112/EC',
    'VATEX-EU-151-1C': 'Exempt based on article 151, section 1 (c) of Council Directive 2006/112/EC',
    'VATEX-EU-151-1D': 'Exempt based on article 151, section 1 (d) of Council Directive 2006/112/EC',
    'VATEX-EU-151-1E': 'Exempt based on article 151, section 1 (e) of Council Directive 2006/112/EC',
    'VATEX-EU-153': 'Exempt based on article 153 of Council Directive 2006/112/EC',
    'VATEX-EU-159': 'Exempt based on article 159 of Council Directive 2006/112/EC',
    'VATEX-EU-309': 'Exempt based on article 309 of Council Directive 2006/112/EC',
    'VATEX-EU-AE': 'Reverse charge',
    'VATEX-EU-D': 'Intra-Community acquisition from second hand means of transport',
    'VATEX-EU-F': 'Intra-Community acquisition of second hand goods',
    'VATEX-EU-G': 'Export outside the EU',
    'VATEX-EU-I': 'Intra-Community acquisition of works of art',
    'VATEX-EU-IC': 'Intra-Community supply',
    'VATEX-EU-O': 'Not subject to VAT',
    'VATEX-EU-J': 'Intra-Community acquisition of collectors items and antiques',
    'VATEX-FR-FRANCHISE': 'France domestic VAT franchise in base',
    'VATEX-FR-CNWVAT': 'France domestic Credit Notes without VAT, due to supplier forfeit of VAT for discount',
    'VATEX-FR-CGI261-1': 'Exempt based on 1 of article 261 of the Code Général des Impôts (CGI ; General tax code)',
    'VATEX-FR-CGI261-2': 'Exempt based on 2 of article 261 of the Code Général des Impôts (CGI ; General tax code)',
    'VATEX-FR-CGI261-3': 'Exempt based on 3 of article 261 of the Code Général des Impôts (CGI ; General tax code)',
    'VATEX-FR-CGI261-4': 'Exempt based on 4 of article 261 of the Code Général des Impôts (CGI ; General tax code)',
    'VATEX-FR-CGI261-5': 'Exempt based on 5 of article 261 of the Code Général des Impôts (CGI ; General tax code)',
    'VATEX-FR-CGI261-7': 'Exempt based on 7 of article 261 of the Code Général des Impôts (CGI ; General tax code)',
    'VATEX-FR-CGI261-8': 'Exempt based on 8 of article 261 of the Code Général des Impôts (CGI ; General tax code)',
    'VATEX-FR-CGI261A': 'Exempt based on article 261 A of the Code Général des Impôts (CGI ; General tax code)',
    'VATEX-FR-CGI261B': 'Exempt based on article 261 B of the Code Général des Impôts (CGI ; General tax code)',
    'VATEX-FR-CGI261C-1': 'Exempt based on 1° of article 261 C of the Code Général des Impôts (CGI ; General tax code)',
    'VATEX-FR-CGI261C-2': 'Exempt based on 2° of article 261 C of the Code Général des Impôts (CGI ; General tax code)',
    'VATEX-FR-CGI261C-3': 'Exempt based on 3° of article 261 C of the Code Général des Impôts (CGI ; General tax code)',
    'VATEX-FR-CGI261D-1': 'Exempt based on 1° of article 261 D of the Code Général des Impôts (CGI ; General tax code)',
    'VATEX-FR-CGI261D-1BIS': 'Exempt based on 1°bis of article 261 D of the Code Général des Impôts (CGI ; General tax code)',
    'VATEX-FR-CGI261D-2': 'Exempt based on 2° of article 261 D of the Code Général des Impôts (CGI ; General tax code)',
    'VATEX-FR-CGI261D-3': 'Exempt based on 3° of article 261 D of the Code Général des Impôts (CGI ; General tax code) Exonération de TVA - Article 261 D-3° du Code Général des Impôts',
    'VATEX-FR-CGI261D-4': 'Exempt based on 4° of article 261 D of the Code Général des Impôts (CGI ; General tax code)',
    'VATEX-FR-CGI261E-1': 'Exempt based on 1° of article 261 E of the Code Général des Impôts (CGI ; General tax code)',
    'VATEX-FR-CGI261E-2': 'Exempt based on 2° of article 261 E of the Code Général des Impôts (CGI ; General tax code)',
    'VATEX-FR-CGI277A': 'Exempt based on article 277 A of the Code Général des Impôts (CGI ; General tax code)',
    'VATEX-FR-CGI275': 'Exempt based on article 275 of the Code Général des Impôts (CGI ; General tax code)',
    'VATEX-FR-298SEXDECIESA': 'Exempt based on article 298 sexdecies A of the Code Général des Impôts (CGI ; General tax code)',
    'VATEX-FR-CGI295': 'Exempt based on article 295 of the Code Général des Impôts (CGI ; General tax code)',
    'VATEX-FR-AE': 'Exempt based on 2 of article 283 of the Code Général des Impôts (CGI ; General tax code)',
}

# -------------------------------------------------------------------------
# AREA of countries
# -------------------------------------------------------------------------

GST_COUNTRY_CODES = {
    'AU', 'NZ', 'IN', 'SG', 'MY', 'PK', 'BD', 'LK', 'NP', 'BT', 'PG', 'SA',
    'AG', 'BS', 'BB', 'DM', 'GD', 'JM', 'KN', 'LC', 'VC', 'TT',
}

EUROPEAN_ECONOMIC_AREA_COUNTRY_CODES = {
    # EU Member States
    'AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR', 'DE', 'GR', 'HU', 'IE',
    'IT', 'LV', 'LT', 'LU', 'MT', 'NL', 'PL', 'PT', 'RO', 'SK', 'SI', 'ES', 'SE', 'CH',

    # EFTA Countries in the EEA
    'IS', 'LI', 'NO',
}

COCONTRACTANT_DEFAULT_NOTE = _('Reverse charge: In the absence of a written objection within one month of receipt of the invoice, '
                              'the customer is deemed to acknowledge that they are a taxable person required to file periodic returns. '
                              'If this condition is not met, the customer will be liable for the payment of the tax, interest, '
                              'and penalties due in relation to this condition.')

# -------------------------------------------------------------------------
# SUPPORTED FILE TYPES FOR IMPORT
# -------------------------------------------------------------------------
SUPPORTED_FILE_TYPES = {
    'application/pdf': '.pdf',
    'application/vnd.oasis.opendocument.spreadsheet': '.ods',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
    'image/jpeg': '.jpeg',
    'image/png': '.png',
    'text/csv': '.csv',
}


class FloatFmt(float):
    """ A float with a given precision.
    The precision is used when formatting the float.
    """
    def __new__(cls, value, min_dp=2, max_dp=None):
        return super().__new__(cls, value)

    def __init__(self, value, min_dp=2, max_dp=None):
        self.min_dp = min_dp
        self.max_dp = max_dp

    def __str__(self):
        if not isinstance(self.min_dp, int) or (self.max_dp is not None and not isinstance(self.max_dp, int)):
            return "<FloatFmt()>"
        # why do we round ?
        # imagine we have: 0.499 and max_dp = 2.
        # The best representation for 0.499 with max_dp = 2 is 0.50 not 0.49
        # rounding with max_dp precision ensure we have the best representation with max_dp decimal places.
        self_float = float_round(float(self), self.min_dp if self.max_dp is None else self.max_dp)
        if self.max_dp is None:
            return _float_repr(self_float, self.min_dp)
        else:
            # Format the float to between self.min_dp and self.max_dp decimal places.
            # We start by formatting to self.max_dp, and then remove trailing zeros,
            # but always keep at least self.min_dp decimal places.
            amount_max_dp = _float_repr(self_float, self.max_dp)
            num_trailing_zeros = len(amount_max_dp) - len(amount_max_dp.rstrip('0'))
            return _float_repr(self_float, max(self.max_dp - num_trailing_zeros, self.min_dp))

    def __repr__(self):
        if not isinstance(self.min_dp, int) or (self.max_dp is not None and not isinstance(self.max_dp, int)):
            return "<FloatFmt()>"
        self_float = float(self)
        if self.max_dp is None:
            return f"FloatFmt({self_float!r}, {self.min_dp!r})"
        else:
            return f"FloatFmt({self_float!r}, {self.min_dp!r}, {self.max_dp!r})"


class AccountEdiCommon(object):
    _name = 'account.edi.common'
    _description = "Common functions for EDI documents: generate the data, the constraints, etc"

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    @classmethod
    def _vals_to_etree(cls, vals):
        document_node = vals['document_node']
        return dict_to_xml(document_node, nsmap=document_node['_nsmap'], template=document_node['_template'])

    @classmethod
    def _etree_to_string(cls, tree):
        return etree.tostring(tree, xml_declaration=True, encoding='UTF-8')

    @classmethod
    def _define_document_type(cls, vals, document_type):
        vals['_document_type'] = {
            'name': document_type,
            'model': cls,
        }

    @classmethod
    def _get_document_type(cls, vals):
        return vals.get('_document_type', {}).get('name')

    @classmethod
    def _is_document(cls, vals, *document_types):
        return cls._get_document_type(vals) in document_types

    @classmethod
    def module_installed(cls, module_name):
        """≙ ``module_installed`` (odoo19c: :317-318) — **bloqueado**: IrModule._get() no existe (0 hits)."""
        _blocked('module_installed', 'IrModule._get() no existe (0 hits)')

    @classmethod
    def format_float(cls, amount, precision_digits):
        if amount is None:
            return None
        return _float_repr(float_round(amount, precision_digits), precision_digits)

    @classmethod
    def _get_currency_decimal_places(cls, currency_id):
        # Allows other documents to easily override in case there is a flat max precision number
        return currency_id.decimal_places

    @classmethod
    def _get_uom_unece_code(cls, uom):
        """≙ ``_get_uom_unece_code`` (odoo19c: :328-335) — **bloqueado**: uom.get_external_id() no existe: sin registro de xmlid (0 hits)."""
        _blocked('_get_uom_unece_code', 'uom.get_external_id() no existe: sin registro de xmlid (0 hits)')

    @classmethod
    def _find_value(cls, xpaths, tree, nsmap=False):
        """ Iteratively queries the tree using the xpaths and returns a result as soon as one is found """
        if not isinstance(xpaths, (tuple, list)):
            xpaths = [xpaths]
        for xpath in xpaths:
            # functions from ElementTree like "findtext" do not fully implement xpath, use "xpath" (from lxml) instead
            # (e.g. "//node[string-length(text()) > 5]" raises an invalidPredicate exception with "findtext")
            val = _find_xml_value(xpath, tree, nsmap)
            if val:
                return val

    @classmethod
    def _can_export_selfbilling(cls):
        return False

    @classmethod
    def _get_belgian_cocontractant_note(cls, customer, supplier):
        """≙ ``_get_belgian_cocontractant_note`` (odoo19c: :352-358) — **bloqueado**: depende de _is_cocontractant_fiscal_position, bloqueado."""
        _blocked('_get_belgian_cocontractant_note', 'depende de _is_cocontractant_fiscal_position, bloqueado')

    @classmethod
    def _is_cocontractant_fiscal_position(cls, invoice, customer, supplier):
        """≙ ``_is_cocontractant_fiscal_position`` (odoo19c: :359-365) — **bloqueado**: AccountMove.fiscal_position no existe (0 hits) y ChartTemplate.ref exige company."""
        _blocked('_is_cocontractant_fiscal_position', 'AccountMove.fiscal_position no existe (0 hits) y ChartTemplate.ref exige company')
    # -------------------------------------------------------------------------
    # TAXES
    # -------------------------------------------------------------------------

    @classmethod
    def _validate_taxes(cls, tax_ids):
        """≙ ``_validate_taxes`` (odoo19c: :370-377) — **bloqueado**: AccountTax._validate_repartition_lines() no existe (0 hits)."""
        _blocked('_validate_taxes', 'AccountTax._validate_repartition_lines() no existe (0 hits)')

    @classmethod
    def _get_tax_category_code(cls, customer, supplier, tax):
        """
        Predicts the tax category code for a tax applied to a given base line.
        If the tax has a defined category code, it is returned.
        Otherwise, a reasonable default is provided, though it may not always be accurate.

        Source: doc of Peppol (but the CEF norm is also used by factur-x, yet not detailed)
        https://docs.peppol.eu/poacc/billing/3.0/syntax/ubl-invoice/cac-TaxTotal/cac-TaxSubtotal/cac-TaxCategory/cbc-TaxExemptionReasonCode/
        https://docs.peppol.eu/poacc/billing/3.0/codelist/vatex/
        https://docs.peppol.eu/poacc/billing/3.0/codelist/UNCL5305/
        """
        # add Norway, Iceland, Liechtenstein
        if not tax:
            return 'E'

        if tax.ubl_cii_tax_category_code:
            return tax.ubl_cii_tax_category_code

        if customer.country.code == 'ES' and customer.zip:
            if customer.zip[:2] in ('35', '38'):  # Canary
                # [BR-IG-10]-A VAT breakdown (BG-23) with VAT Category code (BT-118) "IGIC" shall not have a VAT
                # exemption reason code (BT-121) or VAT exemption reason text (BT-120).
                return 'L'
            if customer.zip[:2] in ('51', '52'):
                return 'M'  # Ceuta & Mellila

        if supplier.country == customer.country:
            if not tax or tax.amount == 0:
                # in theory, you should indicate the precise law article
                return 'E'
            elif tax.has_negative_factor:
                # Special case: Purchase reverse-charge taxes for self-billed invoices.
                # From the buyer's perspective, this is a standard tax with a non-zero percentage but
                # two tax repartition lines that cancel each other out.
                # But from the seller's perspective, this is a zero-percent tax (VAT liability is deferred
                # to the buyer).
                # For a self-billed invoice we, the buyer, create the invoice on behalf of the seller.
                # So in the XML we put the zero-percent tax with code 'AE' that the seller would have used.
                return 'AE'
            else:
                return 'S'  # standard VAT

        if supplier.country.code in EUROPEAN_ECONOMIC_AREA_COUNTRY_CODES and supplier.vat:
            if tax.amount != 0 and not tax.has_negative_factor:
                # Special case: Purchase reverse-charge taxes for self-billed invoices.
                # See explanation above.
                # In the XML we put the zero-percent tax with code 'G' or 'K' that the buyer would have used.
                return 'S'
            if customer.country.code not in EUROPEAN_ECONOMIC_AREA_COUNTRY_CODES:
                return 'G'
            if customer.country.code in EUROPEAN_ECONOMIC_AREA_COUNTRY_CODES:
                return 'K'

        if tax.amount != 0:
            return 'S'
        else:
            return 'E'

    @classmethod
    def _get_tax_exemption_reason(cls, customer, supplier, tax):
        """ Returns the reason and code from the tax if available.
            If not, it falls back to the default tax exemption reason defined for the respective tax category code.

            Note: In Peppol, taxes should be grouped by tax category code but *not* by
            exemption reason, see https://docs.peppol.eu/poacc/billing/3.0/bis/#_calculation_of_vat
        """

        if reason := tax and not tax.amount and cls._get_belgian_cocontractant_note(customer, supplier):
            return {
                'tax_exemption_reason_code': 'VATEX-EU-AE',
                'tax_exemption_reason': reason,
            }

        if tax and (code := tax.ubl_cii_tax_exemption_reason_code):
            return {
                'tax_exemption_reason_code': code,
                'tax_exemption_reason': TAX_EXEMPTION_MAPPING.get(code, _("Exempt from tax") if tax.ubl_cii_requires_exemption_reason else None),
            }

        tax_category_code = cls._get_tax_category_code(customer, supplier, tax)
        tax_exemption_reason = tax_exemption_reason_code = None

        if not tax or tax_category_code == 'E':
            tax_exemption_reason = _("Exempt from tax")
        elif tax_category_code == 'G':
            tax_exemption_reason = _('Export outside the EU')
            tax_exemption_reason_code = 'VATEX-EU-G'
        elif tax_category_code == 'K':
            tax_exemption_reason = _('Intra-Community supply')
            tax_exemption_reason_code = 'VATEX-EU-IC'

        return {
            'tax_exemption_reason': tax_exemption_reason,
            'tax_exemption_reason_code': tax_exemption_reason_code,
        }

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------

    @classmethod
    def _check_required_fields(cls, record, field_names, custom_warning_message=""):
        """Check if at least one of the field_names are set on the record/dict

        :param record: either a recordSet or a dict
        :param field_names: The field name or list of field name that has to
                            be checked. If a list is provided, check that at
                            least one of them is set.
        :return: an Error message or None
        """
        if not record:
            return custom_warning_message or _("The element %(record)s is required on %(field_list)s.", record=record, field_list=field_names)

        if not isinstance(field_names, (list, tuple)):
            field_names = (field_names,)

        has_values = any((field_name in record and record[field_name]) for field_name in field_names)
        # field is present
        if has_values:
            return

        # field is not present
        if custom_warning_message or isinstance(record, dict):
            return custom_warning_message or _(
                "The element %(record)s is required on %(field_list)s.",
                record=record,
                field_list=field_names,
            )

        # DIVERGENCIA: ``record.fields_get(names)`` (introspección de Odoo,
        # devuelve ``{campo: {'string': etiqueta}}``) → ``Meta`` de Django, que
        # lleva la misma etiqueta en ``verbose_name``. ``display_name`` →
        # ``str(record)``, que es lo que ``__str__`` produce en este árbol.
        display_field_names = {name: cls._field_label(record, name)
                               for name in field_names}
        if len(field_names) == 1:
            display_field = f"'{display_field_names[field_names[0]]}'"
            return _("The field %(field)s is required on %(record)s.", field=display_field, record=str(record))
        else:
            display_fields = [f"'{display_field_names[x]}'" for x in display_field_names]
            return _("At least one of the following fields %(field_list)s is required on %(record)s.", field_list=display_fields, record=str(record))

    @classmethod
    def _field_label(cls, record, name):
        """La etiqueta legible de un campo — sustituto de ``fields_get``.

        Añadido en el porte (no está en la referencia): allí la
        introspección es una sola llamada al ORM; aquí se lee de
        ``Meta``. Se declara como símbolo nuevo, no como equivalente de
        ninguno de los 41 de la fuente.
        """
        try:
            return record._meta.get_field(name).verbose_name
        except Exception:
            return name

    # -------------------------------------------------------------------------
    # COMMON CONSTRAINTS
    # -------------------------------------------------------------------------

    @classmethod
    def _invoice_constraints_common(cls, invoice):
        # check that there is a tax on each line
        """≙ ``_invoice_constraints_common`` (odoo19c: :508-513) — **bloqueado**: AccountMove.invoice_line_ids no existe (0 hits)."""
        _blocked('_invoice_constraints_common', 'AccountMove.invoice_line_ids no existe (0 hits)')

    # -------------------------------------------------------------------------
    # Import invoice
    # -------------------------------------------------------------------------

    @classmethod
    def _import_invoice_ubl_cii(cls, invoice, file_data, new=False):
        """≙ ``_import_invoice_ubl_cii`` (odoo19c: :519-575) — **bloqueado**: AccountMove._get_edi_creation/is_purchase_document/_reason_cannot_decode_has_invoice_lines no existen (0 hits)."""
        _blocked('_import_invoice_ubl_cii', 'AccountMove._get_edi_creation/is_purchase_document/_reason_cannot_decode_has_invoice_lines no existen (0 hits)')

    @classmethod
    def _add_logs_import_invoice_ubl_cii(cls, invoice, invoice_logs=None):
        """≙ ``_add_logs_import_invoice_ubl_cii`` (odoo19c: :577-583) — **bloqueado**: IrModel._get() no existe (0 hits)."""
        _blocked('_add_logs_import_invoice_ubl_cii', 'IrModel._get() no existe (0 hits)')

    @classmethod
    def _log_import_invoice_ubl_cii(cls, invoice, title_logs=None, invoice_logs=None, attachments=None):
        """≙ ``_log_import_invoice_ubl_cii`` (odoo19c: :585-591) — **bloqueado**: AccountMove no hereda MailThread: message_post no le llega."""
        _blocked('_log_import_invoice_ubl_cii', 'AccountMove no hereda MailThread: message_post no le llega')

    @classmethod
    def _import_attachments(cls, invoice, tree):
        # Import the embedded documents in the xml if some are found
        """≙ ``_import_attachments`` (odoo19c: :593-629) — **bloqueado**: AccountMove.message_main_attachment_id/_message_set_main_attachment_id no existen (0 hits)."""
        _blocked('_import_attachments', 'AccountMove.message_main_attachment_id/_message_set_main_attachment_id no existen (0 hits)')

    @classmethod
    def _import_partner(cls, company_id, name, phone, email, vat, *, peppol_eas=False, peppol_endpoint=False, postal_address={}, **kwargs):
        """≙ ``_import_partner`` (odoo19c: :631-668) — **bloqueado**: ResPartner._retrieve_partner/_run_vat_checks/with_company no existen (0 hits)."""
        _blocked('_import_partner', 'ResPartner._retrieve_partner/_run_vat_checks/with_company no existen (0 hits)')

    @classmethod
    def _import_partner_bank(cls, invoice, bank_details):
        """≙ ``_import_partner_bank`` (odoo19c: :670-690) — **bloqueado**: ResPartnerBank._find_or_create_bank_account y AccountMove._message_log no existen (0 hits)."""
        _blocked('_import_partner_bank', 'ResPartnerBank._find_or_create_bank_account y AccountMove._message_log no existen (0 hits)')

    @classmethod
    def _import_document_allowance_charges(cls, tree, record, tax_type, qty_factor=1):
        """≙ ``_import_document_allowance_charges`` (odoo19c: :692-737) — **bloqueado**: AccountTax._check_company_domain y AccountMove._get_line_vals_list no existen (0 hits)."""
        _blocked('_import_document_allowance_charges', 'AccountTax._check_company_domain y AccountMove._get_line_vals_list no existen (0 hits)')

    @classmethod
    def _import_currency(cls, tree, xpath):
        logs = []
        currency_name = tree.findtext(xpath)
        # DIVERGENCIA: ``env.company.currency_id`` → ``currency`` de la empresa
        # activa; ``with_context(active_test=False)`` no tiene análogo (este
        # árbol no filtra por ``active`` de forma implícita, así que la
        # búsqueda ya ve las divisas archivadas y el contexto sobra).
        company = env.company
        currency = getattr(company, 'currency', None) if company else None
        if currency_name is not None:
            currency = env['res.currency'].search([
                ('name', '=', currency_name),
            ], limit=1)
            if currency:
                if not currency.active:
                    logs.append(_("The currency '%s' is not active.", currency.name))
            else:
                logs.append(_("Could not retrieve currency: %s. Did you enable the multicurrency option "
                              "and activate the currency?", currency_name))
        return (currency.id if currency else None), logs

    @classmethod
    def _import_description(cls, tree, xpaths):
        description = ""
        for xpath in xpaths:
            note = tree.findtext(xpath)
            if note:
                description += f"<p>{html_escape(note)}</p>"
        return description

    @classmethod
    def _import_prepaid_amount(cls, invoice, tree, xpath, qty_factor):
        logs = []
        prepaid_amount = float(tree.findtext(xpath) or 0)
        # DIVERGENCIA: ``formatLang`` (formato por locale) → ``_format_lang_amount``
        # y ``currency_id`` → ``currency`` (este árbol no lleva el sufijo).
        if not invoice.currency.is_zero(prepaid_amount):
            amount = prepaid_amount * qty_factor
            formatted_amount = _format_lang_amount(amount, invoice.currency)
            logs.append(_("A payment of %s was detected.", formatted_amount))
        return logs

    @classmethod
    def _import_lines(cls, record, tree, xpath, document_type=False, tax_type=False, qty_factor=1):
        """≙ ``_import_lines`` (odoo19c: :771-786) — **bloqueado**: with_company() no existe y _retrieve_taxes esta bloqueado."""
        _blocked('_import_lines', 'with_company() no existe y _retrieve_taxes esta bloqueado')

    @classmethod
    def _import_rounding_amount(cls, invoice, tree, xpath, document_type=False, qty_factor=1):
        """≙ ``_import_rounding_amount`` (odoo19c: :788-822) — **bloqueado**: AccountMove.amount_total_signed/direction_sign no existen (0 hits)."""
        _blocked('_import_rounding_amount', 'AccountMove.amount_total_signed/direction_sign no existen (0 hits)')

    @classmethod
    def _retrieve_invoice_line_vals(cls, tree, document_type=False, qty_factor=1):
        # Start and End date (enterprise fields)
        """≙ ``_retrieve_invoice_line_vals`` (odoo19c: :824-847) — **bloqueado**: AccountMoveLine._fields (introspeccion Odoo) y _retrieve_line_vals bloqueado."""
        _blocked('_retrieve_invoice_line_vals', 'AccountMoveLine._fields (introspeccion Odoo) y _retrieve_line_vals bloqueado')

    @classmethod
    def _retrieve_rebate_val(cls, tree, xpath_dict, quantity):
        # Discount. /!\ as no percent discount can be set on a line, need to infer the percentage
        # from the amount of the actual amount of the discount (the allowance charge)
        rebate = 0
        rebate_node = tree.find(xpath_dict['rebate'])
        net_price_unit_node = tree.find(xpath_dict['net_price_unit'])
        gross_price_unit_node = tree.find(xpath_dict['gross_price_unit'])
        if rebate_node is not None:
            rebate = float(rebate_node.text)
        elif net_price_unit_node is not None and gross_price_unit_node is not None:
            rebate = float(gross_price_unit_node.text) - float(net_price_unit_node.text)
        return rebate

    @classmethod
    def _retrieve_charge_allowance_vals(cls, tree, xpath_dict, quantity):
        charges = []
        discount_amount = 0
        for allowance_charge_node in tree.iterfind(xpath_dict['allowance_charge']):
            charge_indicator = allowance_charge_node.findtext(xpath_dict['allowance_charge_indicator']) or 'false'
            amount = float(allowance_charge_node.findtext(xpath_dict['allowance_charge_amount'], default='0'))
            reason_code = allowance_charge_node.findtext(xpath_dict['allowance_charge_reason_code'], default='')
            reason = allowance_charge_node.findtext(xpath_dict['allowance_charge_reason'], default='')
            if charge_indicator.lower() == 'true':
                charges.append({
                    'amount': amount,
                    'line_quantity': quantity,
                    'reason': reason,
                    'reason_code': reason_code,
                })
            else:
                discount_amount += amount
        return discount_amount, charges

    @classmethod
    def _retrieve_line_vals(cls, tree, document_type=False, qty_factor=1):
        """≙ ``_retrieve_line_vals`` (odoo19c: :880-1002) — **bloqueado**: _import_product bloqueado y env.ref de uom sin registro de xmlid."""
        _blocked('_retrieve_line_vals', '_import_product bloqueado y env.ref de uom sin registro de xmlid')

    @classmethod
    def _import_product(cls, **product_vals):
        """≙ ``_import_product`` (odoo19c: :1004-1005) — **bloqueado**: ProductProduct._retrieve_product() no existe (0 hits)."""
        _blocked('_import_product', 'ProductProduct._retrieve_product() no existe (0 hits)')

    @classmethod
    def _retrieve_fixed_tax(cls, company_id, fixed_tax_vals):
        """≙ ``_retrieve_fixed_tax`` (odoo19c: :1007-1029) — **bloqueado**: AccountJournal._check_company_domain() no existe (0 hits)."""
        _blocked('_retrieve_fixed_tax', 'AccountJournal._check_company_domain() no existe (0 hits)')

    @classmethod
    def _retrieve_taxes(cls, record, line_values, tax_type, tax_exigibility=None):
        """≙ ``_retrieve_taxes`` (odoo19c: :1031-1091) — **bloqueado**: AccountJournal._check_company_domain y AccountMove.fiscal_position no existen (0 hits)."""
        _blocked('_retrieve_taxes', 'AccountJournal._check_company_domain y AccountMove.fiscal_position no existen (0 hits)')

    @classmethod
    def _retrieve_line_charges(cls, record, line_values, taxes):
        """≙ ``_retrieve_line_charges`` (odoo19c: :1093-1121) — **bloqueado**: AccountMove._get_line_vals_list() no existe (0 hits)."""
        _blocked('_retrieve_line_charges', 'AccountMove._get_line_vals_list() no existe (0 hits)')

    @classmethod
    def _get_document_allowance_charge_xpaths(cls):
        # OVERRIDE
        pass

    @classmethod
    def _get_invoice_line_xpaths(cls, invoice_line, qty_factor):
        # OVERRIDE
        pass

    @classmethod
    def _correct_invoice_tax_amount(cls, tree, invoice):
        pass  # To be implemented by the format if needed
