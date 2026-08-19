r"""``account.tax`` — lo que ``account_edi_ubl_cii`` le cuelga (≙ ``_inherit``).

Adaptación de ``odoo19c: addons/account_edi_ubl_cii/models/account_tax.py``
(``odoo-tools@622ddc2a``, LGPL-3, 128 líneas) — atribución y aviso de licencia
preservados (DEC-KX-03).

Cobertura: 5 de 5 símbolos presentes — 3 campos + 2 métodos
============================================================

.. list-table::
   :header-rows: 1
   :widths: 40 14 46

   * - Símbolo
     - Estado
     - Nota
   * - ``ubl_cii_tax_category_code``
     - portado
     - ``Selection`` de **10** valores, verbatim
       (:data:`UBL_CII_TAX_CATEGORY_CODES`)
   * - ``ubl_cii_tax_exemption_reason_code``
     - portado
     - ``Selection`` de **88** valores, verbatim
       (:data:`UBL_CII_TAX_EXEMPTION_REASON_CODES`)
   * - ``ubl_cii_requires_exemption_reason``
     - portado
     - ``compute`` sin ``store`` → ``property``
   * - ``_compute_ubl_cii_requires_exemption_reason``
     - portado
     - es el cuerpo de esa ``property``; el ``@api.depends`` de la fuente lo
       expresa el propio acceso (una ``property`` se recalcula siempre, así
       que la dependencia declarada sobra)
   * - ``_onchange_ubl_cii_tax_category_code``
     - **divergencia declarada**
     - ``@api.onchange`` es un mecanismo de **formulario web**: la referencia
       lo dispara al cambiar el campo en la vista, antes de guardar. Este
       árbol no tiene ese canal (0 hits de ``onchange`` disparado por vista),
       así que el método se instala y **se puede invocar**, pero nadie lo
       llama solo. Se conserva su efecto verbatim —limpiar la razón de
       exención cuando la categoría deja de exigirla— para que el consumidor
       que porte el formulario lo tenga listo

Estos tres campos son exactamente los que ``account_edi_common.py`` lee en
``_get_tax_category_code`` y ``_get_tax_exemption_reason`` (ambos portados);
sin ellos esos dos métodos verían ``AttributeError``. Son, por tanto, la
pieza que hace que la mitad *portada* del addon funcione de verdad.

Los dos ``Selection`` se cuelgan sobre ``account.AccountTax`` con
``add_field_if_absent``, el mismo mecanismo que ``account_peppol`` usa para
``peppol_verification_state`` sobre ``base.ResPartner``.
"""
import fields
from orm.method_chain import chain_method
from orm.model_classes import add_field_if_absent

from addons.account.models.account_tax import AccountTax

#: ≙ el ``selection`` de ``ubl_cii_tax_category_code`` (``odoo19c: :10-21``).
UBL_CII_TAX_CATEGORY_CODES = [
    ('AE', 'AE - Vat Reverse Charge'),
    ('E', 'E - Exempt from Tax'),
    ('S', 'S - Standard rate'),
    ('Z', 'Z - Zero rated goods'),
    ('G', 'G - Free export item, VAT not charged'),
    ('O', 'O - Services outside scope of tax'),
    ('K', 'K - VAT exempt for EEA intra-community supply of goods and services'),
    ('L', 'L - Canary Islands general indirect tax'),
    ('M', 'M - Tax for production, services and importation in Ceuta and Melilla'),
    ('B', 'B - Transferred (VAT), In Italy'),
]

#: ≙ el ``selection`` de ``ubl_cii_tax_exemption_reason_code``
#: (``odoo19c: :23-119``).
UBL_CII_TAX_EXEMPTION_REASON_CODES = [
    ('VATEX-EU-79-C', 'VATEX-EU-79-C - Exempt based on article 79, point c of Council Directive 2006/112/EC'),
    ('VATEX-EU-132', 'VATEX-EU-132 - Exempt based on article 132 of Council Directive 2006/112/EC'),
    ('VATEX-EU-132-1A', 'VATEX-EU-132-1A - Exempt based on article 132, section 1 (a) of Council Directive 2006/112/EC'),
    ('VATEX-EU-132-1B', 'VATEX-EU-132-1B - Exempt based on article 132, section 1 (b) of Council Directive 2006/112/EC'),
    ('VATEX-EU-132-1C', 'VATEX-EU-132-1C - Exempt based on article 132, section 1 (c) of Council Directive 2006/112/EC'),
    ('VATEX-EU-132-1D', 'VATEX-EU-132-1D - Exempt based on article 132, section 1 (d) of Council Directive 2006/112/EC'),
    ('VATEX-EU-132-1E', 'VATEX-EU-132-1E - Exempt based on article 132, section 1 (e) of Council Directive 2006/112/EC'),
    ('VATEX-EU-132-1F', 'VATEX-EU-132-1F - Exempt based on article 132, section 1 (f) of Council Directive 2006/112/EC'),
    ('VATEX-EU-132-1G', 'VATEX-EU-132-1G - Exempt based on article 132, section 1 (g) of Council Directive 2006/112/EC'),
    ('VATEX-EU-132-1H', 'VATEX-EU-132-1H - Exempt based on article 132, section 1 (h) of Council Directive 2006/112/EC'),
    ('VATEX-EU-132-1I', 'VATEX-EU-132-1I - Exempt based on article 132, section 1 (i) of Council Directive 2006/112/EC'),
    ('VATEX-EU-132-1J', 'VATEX-EU-132-1J - Exempt based on article 132, section 1 (j) of Council Directive 2006/112/EC'),
    ('VATEX-EU-132-1K', 'VATEX-EU-132-1K - Exempt based on article 132, section 1 (k) of Council Directive 2006/112/EC'),
    ('VATEX-EU-132-1L', 'VATEX-EU-132-1L - Exempt based on article 132, section 1 (l) of Council Directive 2006/112/EC'),
    ('VATEX-EU-132-1M', 'VATEX-EU-132-1M - Exempt based on article 132, section 1 (m) of Council Directive 2006/112/EC'),
    ('VATEX-EU-132-1N', 'VATEX-EU-132-1N - Exempt based on article 132, section 1 (n) of Council Directive 2006/112/EC'),
    ('VATEX-EU-132-1O', 'VATEX-EU-132-1O - Exempt based on article 132, section 1 (o) of Council Directive 2006/112/EC'),
    ('VATEX-EU-132-1P', 'VATEX-EU-132-1P - Exempt based on article 132, section 1 (p) of Council Directive 2006/112/EC'),
    ('VATEX-EU-132-1Q', 'VATEX-EU-132-1Q - Exempt based on article 132, section 1 (q) of Council Directive 2006/112/EC'),
    ('VATEX-EU-135-1', 'VATEX-EU-135-1 - Exempt based on article 135, section 1 of Council Directive 2006/112/EC'),
    ('VATEX-EU-143', 'VATEX-EU-143 - Exempt based on article 143 of Council Directive 2006/112/EC'),
    ('VATEX-EU-143-1A', 'VATEX-EU-143-1A - Exempt based on article 143, section 1 (a) of Council Directive 2006/112/EC'),
    ('VATEX-EU-143-1B', 'VATEX-EU-143-1B - Exempt based on article 143, section 1 (b) of Council Directive 2006/112/EC'),
    ('VATEX-EU-143-1C', 'VATEX-EU-143-1C - Exempt based on article 143, section 1 (c) of Council Directive 2006/112/EC'),
    ('VATEX-EU-143-1D', 'VATEX-EU-143-1D - Exempt based on article 143, section 1 (d) of Council Directive 2006/112/EC'),
    ('VATEX-EU-143-1E', 'VATEX-EU-143-1E - Exempt based on article 143, section 1 (e) of Council Directive 2006/112/EC'),
    ('VATEX-EU-143-1F', 'VATEX-EU-143-1F - Exempt based on article 143, section 1 (f) of Council Directive 2006/112/EC'),
    ('VATEX-EU-143-1FA', 'VATEX-EU-143-1FA - Exempt based on article 143, section 1 (fa) of Council Directive 2006/112/EC'),
    ('VATEX-EU-143-1G', 'VATEX-EU-143-1G - Exempt based on article 143, section 1 (g) of Council Directive 2006/112/EC'),
    ('VATEX-EU-143-1H', 'VATEX-EU-143-1H - Exempt based on article 143, section 1 (h) of Council Directive 2006/112/EC'),
    ('VATEX-EU-143-1I', 'VATEX-EU-143-1I - Exempt based on article 143, section 1 (i) of Council Directive 2006/112/EC'),
    ('VATEX-EU-143-1J', 'VATEX-EU-143-1J - Exempt based on article 143, section 1 (j) of Council Directive 2006/112/EC'),
    ('VATEX-EU-143-1K', 'VATEX-EU-143-1K - Exempt based on article 143, section 1 (k) of Council Directive 2006/112/EC'),
    ('VATEX-EU-143-1L', 'VATEX-EU-143-1L - Exempt based on article 143, section 1 (l) of Council Directive 2006/112/EC'),
    ('VATEX-EU-144', 'VATEX-EU-144 - Exempt based on article 144 of Council Directive 2006/112/EC'),
    ('VATEX-EU-146-1E', 'VATEX-EU-146-1E - Exempt based on article 146 section 1 (e) of Council Directive 2006/112/EC'),
    ('VATEX-EU-148', 'VATEX-EU-148 - Exempt based on article 148 of Council Directive 2006/112/EC'),
    ('VATEX-EU-148-A', 'VATEX-EU-148-A - Exempt based on article 148, section (a) of Council Directive 2006/112/EC'),
    ('VATEX-EU-148-B', 'VATEX-EU-148-B - Exempt based on article 148, section (b) of Council Directive 2006/112/EC'),
    ('VATEX-EU-148-C', 'VATEX-EU-148-C - Exempt based on article 148, section (c) of Council Directive 2006/112/EC'),
    ('VATEX-EU-148-D', 'VATEX-EU-148-D - Exempt based on article 148, section (d) of Council Directive 2006/112/EC'),
    ('VATEX-EU-148-E', 'VATEX-EU-148-E - Exempt based on article 148, section (e) of Council Directive 2006/112/EC'),
    ('VATEX-EU-148-F', 'VATEX-EU-148-F - Exempt based on article 148, section (f) of Council Directive 2006/112/EC'),
    ('VATEX-EU-148-G', 'VATEX-EU-148-G - Exempt based on article 148, section (g) of Council Directive 2006/112/EC'),
    ('VATEX-EU-151', 'VATEX-EU-151 - Exempt based on article 151 of Council Directive 2006/112/EC'),
    ('VATEX-EU-151-1A', 'VATEX-EU-151-1A - Exempt based on article 151, section 1 (a) of Council Directive 2006/112/EC'),
    ('VATEX-EU-151-1AA', 'VATEX-EU-151-1AA - Exempt based on article 151, section 1 (aa) of Council Directive 2006/112/EC'),
    ('VATEX-EU-151-1B', 'VATEX-EU-151-1B - Exempt based on article 151, section 1 (b) of Council Directive 2006/112/EC'),
    ('VATEX-EU-151-1C', 'VATEX-EU-151-1C - Exempt based on article 151, section 1 (c) of Council Directive 2006/112/EC'),
    ('VATEX-EU-151-1D', 'VATEX-EU-151-1D - Exempt based on article 151, section 1 (d) of Council Directive 2006/112/EC'),
    ('VATEX-EU-151-1E', 'VATEX-EU-151-1E - Exempt based on article 151, section 1 (e) of Council Directive 2006/112/EC'),
    ('VATEX-EU-153', 'VATEX-EU-153 - Exempt based on article 153 of Council Directive 2006/112/EC'),
    ('VATEX-EU-159', 'VATEX-EU-159 - Exempt based on article 159 of Council Directive 2006/112/EC'),
    ('VATEX-EU-309', 'VATEX-EU-309 - Exempt based on article 309 of Council Directive 2006/112/EC'),
    ('VATEX-EU-AE', 'VATEX-EU-AE - Reverse charge'),
    ('VATEX-EU-D', 'VATEX-EU-D - Intra-Community acquisition from second hand means of transport'),
    ('VATEX-EU-F', 'VATEX-EU-F - Intra-Community acquisition of second hand goods'),
    ('VATEX-EU-G', 'VATEX-EU-G - Export outside the EU'),
    ('VATEX-EU-I', 'VATEX-EU-I - Intra-Community acquisition of works of art'),
    ('VATEX-EU-IC', 'VATEX-EU-IC - Intra-Community supply'),
    ('VATEX-EU-O', 'VATEX-EU-O - Not subject to VAT'),
    ('VATEX-EU-J', 'VATEX-EU-J - Intra-Community acquisition of collectors items and antiques'),
    ('VATEX-FR-FRANCHISE', 'VATEX-FR-FRANCHISE - France domestic VAT franchise in base'),
    ('VATEX-FR-CNWVAT', 'VATEX-FR-CNWVAT - France domestic Credit Notes without VAT, due to supplier forfeit of VAT for discount'),
    ('VATEX-FR-CGI261-1', 'VATEX-FR-CGI261-1 - Exempt based on 1 of article 261 of the Code Général des Impôts (CGI ; General tax code)'),
    ('VATEX-FR-CGI261-2', 'VATEX-FR-CGI261-2 - Exempt based on 2 of article 261 of the Code Général des Impôts (CGI ; General tax code)'),
    ('VATEX-FR-CGI261-3', 'VATEX-FR-CGI261-3 - Exempt based on 3 of article 261 of the Code Général des Impôts (CGI ; General tax code)'),
    ('VATEX-FR-CGI261-4', 'VATEX-FR-CGI261-4 - Exempt based on 4 of article 261 of the Code Général des Impôts (CGI ; General tax code)'),
    ('VATEX-FR-CGI261-5', 'VATEX-FR-CGI261-5 - Exempt based on 5 of article 261 of the Code Général des Impôts (CGI ; General tax code)'),
    ('VATEX-FR-CGI261-7', 'VATEX-FR-CGI261-7 - Exempt based on 7 of article 261 of the Code Général des Impôts (CGI ; General tax code)'),
    ('VATEX-FR-CGI261-8', 'VATEX-FR-CGI261-8 - Exempt based on 8 of article 261 of the Code Général des Impôts (CGI ; General tax code)'),
    ('VATEX-FR-CGI261A', 'VATEX-FR-CGI261A - Exempt based on article 261 A of the Code Général des Impôts (CGI ; General tax code)'),
    ('VATEX-FR-CGI261B', 'VATEX-FR-CGI261B - Exempt based on article 261 B of the Code Général des Impôts (CGI ; General tax code)'),
    ('VATEX-FR-CGI261C-1', 'VATEX-FR-CGI261C-1 - Exempt based on 1° of article 261 C of the Code Général des Impôts (CGI ; General tax code)'),
    ('VATEX-FR-CGI261C-2', 'VATEX-FR-CGI261C-2 - Exempt based on 2° of article 261 C of the Code Général des Impôts (CGI ; General tax code)'),
    ('VATEX-FR-CGI261C-3', 'VATEX-FR-CGI261C-3 - Exempt based on 3° of article 261 C of the Code Général des Impôts (CGI ; General tax code)'),
    ('VATEX-FR-CGI261D-1', 'VATEX-FR-CGI261D-1 - Exempt based on 1° of article 261 D of the Code Général des Impôts (CGI ; General tax code)'),
    ('VATEX-FR-CGI261D-1BIS', 'VATEX-FR-CGI261D-1BIS - Exempt based on 1°bis of article 261 D of the Code Général des Impôts (CGI ; General tax code)'),
    ('VATEX-FR-CGI261D-2', 'VATEX-FR-CGI261D-2 - Exempt based on 2° of article 261 D of the Code Général des Impôts (CGI ; General tax code)'),
    ('VATEX-FR-CGI261D-3', 'VATEX-FR-CGI261D-3 - Exempt based on 3° of article 261 D of the Code Général des Impôts (CGI ; General tax code) Exonération de TVA - Article 261 D-3° du Code Général des Impôts'),
    ('VATEX-FR-CGI261D-4', 'VATEX-FR-CGI261D-4 - Exempt based on 4° of article 261 D of the Code Général des Impôts (CGI ; General tax code)'),
    ('VATEX-FR-CGI261E-1', 'VATEX-FR-CGI261E-1 - Exempt based on 1° of article 261 E of the Code Général des Impôts (CGI ; General tax code)'),
    ('VATEX-FR-CGI261E-2', 'VATEX-FR-CGI261E-2 - Exempt based on 2° of article 261 E of the Code Général des Impôts (CGI ; General tax code)'),
    ('VATEX-FR-CGI277A', 'VATEX-FR-CGI277A - Exempt based on article 277 A of the Code Général des Impôts (CGI ; General tax code)'),
    ('VATEX-FR-CGI275', 'VATEX-FR-CGI275 - Exempt based on article 275 of the Code Général des Impôts (CGI ; General tax code)'),
    ('VATEX-FR-298SEXDECIESA', 'VATEX-FR-298SEXDECIESA - Exempt based on article 298 sexdecies A of the Code Général des Impôts (CGI ; General tax code)'),
    ('VATEX-FR-CGI295', 'VATEX-FR-CGI295 - Exempt based on article 295 of the Code Général des Impôts (CGI ; General tax code)'),
    ('VATEX-FR-AE', 'VATEX-FR-AE - Exempt based on 2 of article 283 of the Code Général des Impôts (CGI ; General tax code)'),
]


def _extra_fields():
    """Los dos ``Selection`` con columna real que este addon cuelga.

    ``max_length`` sale de la medición del propio vocabulario (2 y 22
    caracteres el valor más largo de cada uno), no de un número redondo.
    """
    return {
        'ubl_cii_tax_category_code': fields.Selection(
            max_length=2, choices=UBL_CII_TAX_CATEGORY_CODES,
            blank=True, default='',
            verbose_name='Tax Category Code',
            help_text='Código de categoría de IVA usado en facturación '
                      'electrónica (Odoo ubl_cii_tax_category_code).',
        ),
        'ubl_cii_tax_exemption_reason_code': fields.Selection(
            max_length=22, choices=UBL_CII_TAX_EXEMPTION_REASON_CODES,
            blank=True, default='',
            verbose_name='Tax Exemption Reason Code',
            help_text='Razón por la que el importe está exento de IVA o por '
                      'la que no se cobra IVA, usada en facturación '
                      'electrónica (Odoo ubl_cii_tax_exemption_reason_code).',
        ),
    }

#: Las categorías que EXIGEN declarar una razón de exención — ≙ la lista
#: literal de ``_compute_ubl_cii_requires_exemption_reason``
#: (``odoo19c: :123-125``).
_CATEGORIES_REQUIRING_EXEMPTION_REASON = ['AE', 'E', 'G', 'O', 'K']


def _compute_ubl_cii_requires_exemption_reason(self):
    """≙ ``_compute_ubl_cii_requires_exemption_reason`` (``odoo19c: :122-125``).

    ``compute`` sin ``store`` → ``property``: el bucle ``for tax in self`` de
    la fuente desaparece porque aquí ``self`` es un registro, no un recordset.
    """
    return self.ubl_cii_tax_category_code in \
        _CATEGORIES_REQUIRING_EXEMPTION_REASON


def _onchange_ubl_cii_tax_category_code(self):
    """≙ ``_onchange_ubl_cii_tax_category_code`` (``odoo19c: :127-131``).

    Ver la nota de la tabla del docstring: el ``@api.onchange`` de la fuente es
    un canal de formulario web que este árbol no tiene. El **efecto** se porta
    verbatim y el método queda invocable; lo que no existe es el disparo
    automático al editar el campo en una vista.
    """
    if not self.ubl_cii_requires_exemption_reason:
        self.ubl_cii_tax_exemption_reason_code = ''


def apply_account_edi_ubl_cii_account_tax_extensions():
    """Cuelga sobre ``account.AccountTax`` los tres campos UBL/CII — ≙
    ``_inherit = 'account.tax'``. La llama ``AccountEdiUblCiiConfig.ready()``."""
    for name, field in _extra_fields().items():
        add_field_if_absent(AccountTax, name, field)

    if not hasattr(AccountTax, 'ubl_cii_requires_exemption_reason'):
        AccountTax.ubl_cii_requires_exemption_reason = property(
            _compute_ubl_cii_requires_exemption_reason)

    chain_method(AccountTax, '_onchange_ubl_cii_tax_category_code',
                 _onchange_ubl_cii_tax_category_code)


__all__ = [
    'UBL_CII_TAX_CATEGORY_CODES',
    'UBL_CII_TAX_EXEMPTION_REASON_CODES',
    'apply_account_edi_ubl_cii_account_tax_extensions',
]
