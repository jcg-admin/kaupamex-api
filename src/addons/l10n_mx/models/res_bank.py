r"""``res.bank``/``res.partner.bank`` — lo que ``l10n_mx`` les cuelga (≙ ``_inherit``).

Adaptado de Odoo Community ``l10n_mx/models/res_bank.py`` (LGPL-3,
``odoo-tools@622ddc2a``, ``odoo19c:``) — atribución y aviso de licencia
preservados (DEC-KX-03).

Dos clases, cuatro campos: qué se porta y qué no
=================================================

La referencia declara **dos** clases (``ResBank``/``ResPartnerBank``, en el
árbol ``base``, ya portadas en ``base/models/res_bank.py`` y
``base/models/res_partner_bank.py``) y les cuelga, cada una, un campo propio
más una repetición del mismo cómputo:

================  ========================  ================================
Clase             Campo                     Qué es
================  ========================  ================================
``ResBank``       ``l10n_mx_edi_code``      Char — código ABM. **Se porta.**
``ResBank``       ``fiscal_country_codes``  Derivado de sesión. **Se porta.**
``ResPartnerBank``\ ``l10n_mx_edi_clabe``   Char — CLABE. **Se porta.**
``ResPartnerBank``\ ``fiscal_country_codes``\ Derivado de sesión. **Se porta.**
================  ========================  ================================

``l10n_mx_edi_code`` y ``l10n_mx_edi_clabe`` son columnas propias, sin
dependencia de nada ausente — se cuelgan igual que en la referencia.

``fiscal_country_codes`` — desbloqueado, y no vive aquí
========================================================

En la referencia es ``fields.Char(store=False, default=_get_fiscal_country_codes)``,
y ``_get_fiscal_country_codes`` hace
``','.join(self.env.companies.mapped('account_fiscal_country_id.code'))``:
concatena el código de país fiscal de las empresas activadas de la sesión.

Una versión anterior de este archivo lo declaraba **bloqueado** porque
``ResCompany`` no tenía ``account_fiscal_country``. Ese campo ya existe
(``account/models/res_company.py``, ``base/0018``), así que el bloqueo se
levanta.

**El mecanismo se cuelga desde ``account``, no desde aquí**, y la razón es de
la referencia: ``fiscal_country_codes`` no es un símbolo de la localización
mexicana. ``odoo19c`` lo declara en **diez clases** repartidas por el árbol —
cinco en ``account`` (``res_currency``, ``product``, ``account_payment_term``,
``partner``, ``uom_uom``), dos aquí, y tres más en otras localizaciones
(``l10n_cl``, ``l10n_ec_sale``). Colgarlo desde ``l10n_mx`` haría que el
código ABM de un banco mexicano fuera precondición de un campo que
``res.currency`` necesita igual.

Por eso ``account/models/res_company.py`` cuelga la ``property`` sobre
``ResBank`` y ``ResPartnerBank`` junto con las otras cuatro: allí está el
campo del que deriva, y allí está su única definición.

Los dos ``_get_fiscal_country_codes`` de la referencia —uno por clase, mismo
cuerpo— se portan como **un** ayudante compartido
(``account.models.res_company.get_fiscal_country_codes``), no duplicado. La
referencia los repite porque su ``default=`` necesita un método en la clase;
este ORM no tiene ese constructor, así que repetir el cuerpo sería copiar una
restricción ajena en vez de la conducta.
"""
import fields

from addons.base.models.res_bank import ResBank
from addons.base.models.res_partner_bank import ResPartnerBank


def _add_if_absent(model, name, field):
    """Cuelga el campo sólo si el modelo no lo tiene ya.

    Idempotente a propósito: ``ready()`` puede correr más de una vez en un
    proceso (recarga del autoreloader), y ``add_to_class`` sobre un campo que
    ya existe rompe con ``FieldError``. Mismo helper que
    ``account/models/res_company.py``.
    """
    if not any(f.name == name for f in model._meta.get_fields()):
        model.add_to_class(name, field)


def apply_l10n_mx_extensions():
    """≙ ``_inherit = 'res.bank'`` + ``_inherit = 'res.partner.bank'`` de
    ``l10n_mx`` (``odoo19c: l10n_mx/models/res_bank.py``).

    Se llama desde ``L10nMxConfig.ready()``, no al importar: en tiempo de
    import el registro de modelos aún no está poblado.
    """
    _add_if_absent(ResBank, 'l10n_mx_edi_code', fields.Char(
        max_length=3, blank=True, default='',
        help_text='Número de tres dígitos que la ABM asigna a las '
                  'instituciones bancarias (Odoo l10n_mx_edi_code; ABM = '
                  'Asociación de Bancos de México).',
    ))
    _add_if_absent(ResPartnerBank, 'l10n_mx_edi_clabe', fields.Char(
        max_length=18, blank=True, default='',
        help_text='CLABE — cifra bancaria estandarizada de México (Odoo '
                  'l10n_mx_edi_clabe).',
    ))
