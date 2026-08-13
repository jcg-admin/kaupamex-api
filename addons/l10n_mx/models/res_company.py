"""``res.company`` — lo que ``l10n_mx`` le cuelga (≙ ``_inherit``).

Adaptado de Odoo Community ``l10n_mx/models/res_company.py`` (LGPL-3,
``odoo-tools@622ddc2a``, ``odoo19c:``) — atribución y aviso de licencia
preservados (DEC-KX-03).

Dos campos, los dos se portan
==============================

La referencia cuelga dos ``Many2one`` a ``account.account`` — sin ``compute``,
sin ``related``, sin dependencia de nada ausente:

- ``l10n_mx_income_return_discount_account_id`` — cuenta de ingresos para
  devoluciones y descuentos.
- ``l10n_mx_income_re_invoicing_account_id`` — cuenta de ingresos para
  re-facturación.

``account.AccountAccount`` ya existe en este árbol
(``account/models/account_account.py``), así que ambos se cuelgan igual que
los pares ``_default_tax``/cuentas de utilidad que
``account/models/res_company.py`` ya cuelga sobre el mismo ``ResCompany`` —
mismo helper ``_add_if_absent``, mismo criterio de ``on_delete``.

``on_delete=PROTECT`` y no ``SET_NULL``: la referencia no declara
``ondelete`` para estos dos M2M (usa el default de Odoo, ``restrict``) —
borrar una cuenta que es el destino fiscal configurado de una empresa debe
fallar la operación, no dejar la configuración fiscal en silencio con un
``NULL``. Mismo razonamiento que ``_default_tax`` en
``account/models/res_company.py``.
"""
from django.db import models as dj_models

import fields

from addons.base.models.res_company import ResCompany


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
    """≙ ``_inherit = 'res.company'`` de ``l10n_mx``
    (``odoo19c: l10n_mx/models/res_company.py``).

    Se llama desde ``L10nMxConfig.ready()``, no al importar: en tiempo de
    import el registro de modelos aún no está poblado.
    """
    _add_if_absent(ResCompany, 'l10n_mx_income_return_discount_account', fields.Many2one(
        'account.AccountAccount',
        null=True, blank=True, on_delete=dj_models.PROTECT, related_name='+',
        help_text='Cuenta de ingresos para devoluciones y descuentos (Odoo '
                  'l10n_mx_income_return_discount_account_id).',
    ))
    _add_if_absent(ResCompany, 'l10n_mx_income_re_invoicing_account', fields.Many2one(
        'account.AccountAccount',
        null=True, blank=True, on_delete=dj_models.PROTECT, related_name='+',
        help_text='Cuenta de ingresos para re-facturación (Odoo '
                  'l10n_mx_income_re_invoicing_account_id).',
    ))
