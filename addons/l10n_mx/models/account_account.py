"""``account.account`` — etiqueta de naturaleza deudora/acreedora (Odoo ``l10n_mx``).

Adaptado de Odoo Community ``l10n_mx/models/account_account.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3) — DEC-KX-03.

Porte completo: la referencia declara **1 método** (``create``) sobre
``account.account`` y no declara campos propios. Se cuelga aquí.

Qué hace, con las dos etiquetas que necesita
=============================================

Al crear una cuenta de una empresa mexicana sin etiqueta de saldo, la
referencia le asigna una de dos etiquetas maestras —
``l10n_mx.tag_debit_balance_account`` / ``l10n_mx.tag_credit_balance_account``—
según el primer dígito de su código: ``1``/``5``/``6``/``7`` es saldo deudor
(``DEBIT_CODES``); cualquier otro, acreedor. Esas dos filas de
``account.account.tag`` las siembra el ``data/`` de ``l10n_mx`` (fuera del
alcance de este archivo — ver Bloque 0, no portado en este pase); mientras no
existan, ``IrModelData.ref(..., raise_if_not_found=False)`` devuelve ``None``
y el receptor sale sin efecto, **igual que la referencia** (``if not
debit_tag or not credit_tag: return accounts``).

Tres divergencias declaradas, ninguna de alcance
==================================================

**No hay ``create(vals_list)`` que extender.** ``api: src/addons/account/
models/account_account.py`` no sobreescribe ``create()`` — el punto de
extensión Odoo (``@api.model_create_multi``) no tiene análogo directo aquí.
El equivalente idiomático ya establecido en este puerto para actuar tras
crear una fila de OTRO addon es la señal ``post_save`` con ``created=True``
(mismo patrón que ``account: models/res_company.py::load_chart_for_new_company``
y ``account: models/product.py::_inherit_company_default_taxes``).

**Una sola empresa, no ``company_ids``.** La referencia lee
``a.company_ids.mapped('country_code')`` — multi-compañía por fila, propio
de su ORM. ``AccountAccount`` de este árbol declara ``company`` como
``Many2one`` único (``api: account_account.py:86-89``), así que el chequeo
es ``instance.company.country_code == 'MX'`` sin ``mapped``.

**``Command.link`` → ``.add()``.** La referencia agrega el id de la etiqueta
con ``account.tag_ids = [Command.link(tag_id)]``; ``tags`` aquí es un
``Many2many`` real de Django — ``instance.tags.add(tag)`` es el equivalente
directo, sin capa de comandos.
"""
from django.db.models.signals import post_save

from addons.account.models import AccountAccount
from addons.base.models.ir_model import IrModelData

#: Primer dígito del código que corresponde a saldo DEUDOR — cualquier otro
#: es acreedor. ≙ ``DEBIT_CODES`` (``odoo19c: l10n_mx/models/
#: account_account.py:17``, ``odoo-tools@622ddc2a``).
DEBIT_CODES = ('1', '5', '6', '7')


def _apply_l10n_mx_balance_tag(sender, instance, created, **kwargs):
    """Etiqueta la cuenta MX nueva con su naturaleza — ≙ el ``create()`` de la referencia.

    ≙ ``odoo19c: l10n_mx/models/account_account.py:7-21``
    (``odoo-tools@622ddc2a``). Sale sin efecto si:

    - la cuenta no es nueva (``created`` falso — la referencia sólo actúa en
      ``create``, nunca en ``write``);
    - las etiquetas maestras aún no existen (``data/`` de ``l10n_mx`` fuera
      de este pase);
    - la empresa de la cuenta no es mexicana;
    - la cuenta ya trae alguna de las dos etiquetas (``not a.tag_ids &
      (credit_tag + debit_tag)`` de la referencia);
    - la cuenta no tiene código todavía (nada de qué leer el primer dígito).
    """
    if not created:
        return
    debit_tag = IrModelData.ref(
        'l10n_mx.tag_debit_balance_account', raise_if_not_found=False)
    credit_tag = IrModelData.ref(
        'l10n_mx.tag_credit_balance_account', raise_if_not_found=False)
    if debit_tag is None or credit_tag is None:
        return
    company = instance.company
    if company is None or company.country_code != 'MX':
        return
    if instance.tags.filter(pk__in=(debit_tag.pk, credit_tag.pk)).exists():
        return
    if not instance.code:
        return
    tag = debit_tag if instance.code[0] in DEBIT_CODES else credit_tag
    instance.tags.add(tag)


def apply_l10n_mx_extensions():
    """≙ ``_inherit = 'account.account'`` de ``l10n_mx`` (``odoo19c:
    l10n_mx/models/account_account.py``).

    Se llama desde ``L10nMxConfig.ready()``, no al importar: en tiempo de
    import el registro de modelos aún no está poblado.
    """
    post_save.connect(
        _apply_l10n_mx_balance_tag, sender=AccountAccount,
        dispatch_uid='l10n_mx.account_account.balance_tag',
    )
