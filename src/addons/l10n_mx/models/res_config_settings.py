"""``res.config.settings`` — lo que ``l10n_mx`` le cuelga (≙ ``_inherit``).

Adaptado de Odoo Community ``l10n_mx/models/res_config_settings.py``
(LGPL-3, ``odoo-tools@622ddc2a``, ``odoo19c:``) — atribución y aviso de
licencia preservados (DEC-KX-03).

El único campo — bloqueado, con su medición
=============================================

La referencia declara un único campo:

.. code-block:: python

    l10n_mx_account_income_return_discount_id = fields.Many2one(
        comodel_name="account.account",
        related='company_id.l10n_mx_income_return_discount_account_id',
        domain="[('account_type', '=', 'income')]",
    )

Es un espejo de sólo-lectura-en-formulario (``readonly=False`` pero
``related=``) del campo que ``res_company.py`` de este mismo addon ya cuelga
sobre ``ResCompany`` — no aporta dato propio, sólo lo expone en el formulario
único de ajustes que Odoo compone fusionando el ``_inherit`` de **todos** los
addons instalados sobre un solo modelo transitorio ``res.config.settings``.

**Ese modelo fusionado no existe en este árbol — medido, no supuesto.**
``base/models/res_config.py`` declara ``ResConfigSettings`` con
``class Meta: abstract = True``: es una base para que **cada addon cree su
propia subclase concreta** (``base_setup.SiteConfigSettings`` es la única que
existe hoy), no un modelo único donde varios addons cuelguen campos con
``add_to_class`` como si fuera ``ResCompany`` o ``ResBank``.

*Métrica:* ``grep -rn "class .*(ResConfigSettings)" src/addons --include=*.py``.
*Ciega a:* un mecanismo de fusión que registrara subclases bajo un mismo
nombre lógico sin que aparezca como herencia directa de ``ResConfigSettings``.
Medido (2026-08-07): **una sola subclase concreta**,
``base_setup.models.res_config_settings.SiteConfigSettings`` — l10n_mx no es
su dueño y no hay ningún otro formulario de ajustes al que asomar este campo.
[PROVEN]

No hay, por tanto, ningún ``model.add_to_class(...)`` válido para este
símbolo: `` _add_if_absent`` cuelga un campo sobre una clase concreta
existente (como hace ``res_bank.py``/``res_company.py`` de este mismo
addon), y aquí esa clase no existe. Fabricar una ``L10nMxConfigSettings``
propia tampoco sería el mismo símbolo: la referencia lo expone en el
formulario **compartido** de ajustes generales, no en uno nuevo que nadie
navegaría — sería inventar superficie, lo que ``porte-completo-no-parcial.md``
prohíbe expresamente.

**DESCONOCIDO con condición de cierre:** el símbolo entra cuando este árbol
tenga un mecanismo de composición de ``res.config.settings`` — un formulario
único que agregue las subclases de todos los addons instalados, análogo al
``_inherit`` fusionado de la referencia — o cuando se decida que la vía
correcta es un campo de sólo-lectura en la propia UI de contabilidad de
México en vez de en el panel de ajustes generales. Ninguna de las dos
decisiones es de este addon: quedan para quien diseñe ese mecanismo.

Símbolos de este archivo: 1 clase (``ResConfigSettings``, la extendida),
0 métodos propios, 1 campo — el único campo queda bloqueado según lo
anterior. 0 de 1 se porta.
"""


def apply_l10n_mx_extensions():
    """≙ ``_inherit = 'res.config.settings'`` de ``l10n_mx``
    (``odoo19c: l10n_mx/models/res_config_settings.py``) — no-op declarado.

    Se llama desde ``L10nMxConfig.ready()`` igual que las demás extensiones
    del addon, para que la lista ``_EXTENSIONES`` sea uniforme y no dependa
    de que el llamador sepa cuáles tienen efecto. El único símbolo de la
    referencia está bloqueado por ausencia de modelo destino — ver el
    docstring del módulo. No cuelga nada porque no hay ninguna clase
    concreta de ``res.config.settings`` a la que colgarle este campo.
    """
    return None
