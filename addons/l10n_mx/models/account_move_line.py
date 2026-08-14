"""``account.move.line`` — cuenta de descuento en notas de crédito MX (Odoo ``l10n_mx``).

Adaptado de Odoo Community ``l10n_mx/models/account_move_line.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3) — DEC-KX-03.

Porte completo: la referencia declara **1 método**
(``_compute_account_id``) sobre ``account.move.line`` y ningún campo. Se
cuelga aquí.

Qué hace
=========

En una nota de crédito de cliente (``move_type='out_refund'``) de una
empresa mexicana, la línea de producto se reimputa a la cuenta de
"descuento por devolución de ingreso" de la empresa, en vez de la cuenta que
le hubiera tocado por producto/categoría — el CFDI mexicano exige separar
ese movimiento del ingreso normal. ≙ ``odoo19c: l10n_mx/models/
account_move_line.py:7-17`` (``odoo-tools@622ddc2a``).

Tres divergencias declaradas, ninguna de alcance
==================================================

**No hay ``_compute_account_id`` base que extender.** La referencia
extiende (``EXTENDS 'account'``) un compute de ``account.move.line`` que
resuelve la cuenta por defecto desde producto/posición fiscal. ``api:
src/addons/account/models/account_move_line.py`` no porta ese compute —
``account`` en ``account`` es un ``Many2one`` plano que el llamador asigna
(ver el docstring de ese archivo). Sin base que llamar por ``super()``, el
punto de enganche es una señal ``pre_save`` (mismo patrón que
``account: models/account_tax.py`` en este mismo addon, y que
``stock: handlers.py::_cache_return_old_status``): se conecta ANTES del
``INSERT``/``UPDATE``, y si las condiciones se cumplen, pisa lo que el
llamador haya puesto en ``account`` — igual que la referencia pisa el valor
que su propio ``super()._compute_account_id()`` acaba de calcular.

**``move_id.country_code`` → ``move.company.country_code``.**
``api: account_move.py`` no declara ``country_code`` propio (no hay
``related`` a país en el asiento). Se deriva de la empresa del asiento
(``base: models/res_company.py:415``, delegado al partner) — mismo criterio
que ``account_tax.py`` de este addon para su propia falta de país.

**``company_id.l10n_mx_income_return_discount_account_id`` — campo de un
archivo hermano, no de éste.** Ese campo lo declara ``l10n_mx/models/
res_company.py`` (fuera de este archivo; otro agente de la misma tanda —
ver ``account: models/res_company.py`` para el precedente del mecanismo).
Este puerto sigue la convención ya fijada ahí de nombrar la FK sin el
sufijo ``_id`` (``account_sale_tax``, no ``account_sale_tax_id``), así que
se lee como ``company.l10n_mx_income_return_discount_account`` con
``getattr(..., None)`` — si el campo aún no existe (orden de import, o el
archivo hermano no llegó a esta tanda), el receptor sale sin efecto en vez
de fallar. **DESCONOCIDO declarado** hasta que ese archivo aterrice: el
receptor queda inerte, no roto.
"""
from django.db.models.signals import pre_save

import api
from addons.account.models import AccountMoveLine


@api.depends('move', 'display_type')
def _compute_account_id(self):
    """Reimputa la línea de producto de una nota de crédito MX — ≙ ``_compute_account_id``.

    ≙ ``odoo19c: l10n_mx/models/account_move_line.py:7-17``
    (``odoo-tools@622ddc2a``). Ver las tres divergencias declaradas en el
    docstring del módulo.
    """
    move = self.move
    if move is None:
        return
    if self.display_type != 'product' or move.move_type != 'out_refund':
        return
    company = move.company
    if company is None or company.country_code != 'MX':
        return
    discount_account = getattr(
        company, 'l10n_mx_income_return_discount_account', None)
    if discount_account:
        self.account = discount_account


def _apply_l10n_mx_income_return_discount(sender, instance, **kwargs):
    """Receptor ``pre_save`` — el punto donde la referencia dispara el compute."""
    _compute_account_id(instance)


def apply_l10n_mx_extensions():
    """≙ ``_inherit = 'account.move.line'`` de ``l10n_mx`` (``odoo19c:
    l10n_mx/models/account_move_line.py``).

    Se llama desde ``L10nMxConfig.ready()``, no al importar: en tiempo de
    import el registro de modelos aún no está poblado.
    """
    pre_save.connect(
        _apply_l10n_mx_income_return_discount, sender=AccountMoveLine,
        dispatch_uid='l10n_mx.account_move_line.income_return_discount',
    )
