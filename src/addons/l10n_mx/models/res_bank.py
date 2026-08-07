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
``ResBank``       ``fiscal_country_codes``  Selection derivado. **Bloqueado.**
``ResPartnerBank``\ ``l10n_mx_edi_clabe``   Char — CLABE. **Se porta.**
``ResPartnerBank``\ ``fiscal_country_codes``\ Selection derivado. **Bloqueado.**
================  ========================  ================================

``l10n_mx_edi_code`` y ``l10n_mx_edi_clabe`` son columnas propias, sin
dependencia de nada ausente — se cuelgan igual que en la referencia.

``fiscal_country_codes`` — bloqueado, con su medición
======================================================

En la referencia es ``fields.Char(store=False, default=_get_fiscal_country_codes)``,
y ``_get_fiscal_country_codes`` hace
``','.join(self.env.companies.mapped('account_fiscal_country_id.code'))``:
concatena el código de país fiscal de las empresas activas de la sesión.

*Métrica:* ``grep -n "account_fiscal_country" src/addons/base/models/res_company.py``.
*Ciega a:* que el campo exista con otro nombre en el mismo modelo.
Medido (2026-08-07): **0 hits** — ``ResCompany`` no declara
``account_fiscal_country_id``. [PROVEN]

Es el mismo campo ausente que ``account/models/res_currency.py`` y
``account/models/product.py`` ya documentan bloqueado por la misma razón — el
Bloque 1 de ``res.company`` (72 campos de la referencia, sólo 2 portados hasta
ahora, ver ``account/models/res_company.py``). **Ya cubierto por la tarea
#137**, que mapea ese bloque campo por campo. No se fabrica aquí una FK ni un
valor calculado que sustituya al campo ausente: eso adelantaría una decisión
que le corresponde a #137 (qué de los 72 campos entra y con qué forma).

Un campo no-store de un solo valor derivado de sesión (``self.env.companies``,
sin fila propia) tampoco tendría equivalente directo en este ORM aunque el
campo destino existiera — no hay ``env`` de sesión sobre el que mapear; el
análogo más cercano es ``orm.environments.get_current_companies()``
(usado por ``base/models/ir_http.py``). Queda anotado para cuando #137 cierre
el campo ausente: en ese momento se decide si ``fiscal_country_codes`` se
expone como ``@property`` que recorra ``get_current_companies()``.

Los dos métodos ``_get_fiscal_country_codes`` (uno por clase en la referencia,
mismo cuerpo) no se portan como funciones colgadas porque no tienen campo al
que servir de ``default`` — colgar el método sin el campo sería un símbolo sin
efecto observable, el mismo anti-patrón que ``porte-completo-no-parcial.md``
señala para métodos "a medias".
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
