"""``res.config.settings`` — declarado NO PORTADO, con su medición.

Adaptación de ``odoo19c: addons/account_check_printing/models/
res_config_settings.py`` (``odoo-tools@622ddc2a``, LGPL-3 — atribución y
aviso de licencia preservados, DEC-KX-03):

.. code-block:: python

    class ResConfigSettings(models.TransientModel):
        _inherit = 'res.config.settings'

        account_check_printing_layout = fields.Selection(
            related='company_id.account_check_printing_layout', readonly=False)
        account_check_printing_date_label = fields.Boolean(
            related='company_id.account_check_printing_date_label', readonly=False)
        account_check_printing_multi_stub = fields.Boolean(
            related='company_id.account_check_printing_multi_stub', readonly=False)
        account_check_printing_margin_top = fields.Float(
            related='company_id.account_check_printing_margin_top', readonly=False)
        account_check_printing_margin_left = fields.Float(
            related='company_id.account_check_printing_margin_left', readonly=False)
        account_check_printing_margin_right = fields.Float(
            related='company_id.account_check_printing_margin_right', readonly=False)

Seis campos, los seis ``related=`` puro — ninguno tiene lógica propia
========================================================================

Los seis son pasarela de escritura hacia ``res.company`` (``related=...,
readonly=False``): existen para que el formulario de Ajustes del cliente
web de Odoo pueda editar los campos de la empresa sin que el usuario
navegue hasta el registro de la compañía. NINGUNO calcula ni valida nada
propio — el DATO real es el que ``models/res_company.py`` YA porta
(``CheckPrintingCompanySettings``, los mismos 6 campos, con la misma
semántica).

Por qué no se porta la CLASE — medido, no supuesto
========================================================

``base/models/res_config.py`` declara ``ResConfigSettings`` con ``class
Meta: abstract = True``: es una base para que CADA addon cree su propia
subclase concreta — no un modelo único donde varios addons cuelguen campos
con ``add_to_class`` como si fuera ``ResCompany``/``ResBank``. Medido:
``grep -rn "class .*(ResConfigSettings)" src/addons --include=*.py`` →
**una sola subclase concreta**, ``base_setup.models.res_config_settings.
SiteConfigSettings`` — consumida por ``base_setup/controllers/`` (DRF).
Ese formulario NO declara ningún campo de este addon (``grep -rn
"account_check_printing" base_setup/`` → **0 hits** [PROVEN]), y no hay
NINGÚN otro consumidor DRF de ``res.config.settings`` en el árbol.

Este es el MISMO caso, con el mismo desenlace, que
``l10n_mx.models.res_config_settings`` ya documenta para su único campo
(``l10n_mx_account_income_return_discount_id``): *"no hay, por tanto,
ningún ``model.add_to_class(...)`` válido para este símbolo... fabricar una
clase propia tampoco sería el mismo símbolo: la referencia lo expone en el
formulario COMPARTIDO de ajustes generales, no en uno nuevo que nadie
navegaría — sería inventar superficie, lo que
``porte-completo-no-parcial.md`` prohíbe expresamente."* Aquí aplica igual,
multiplicado por 6 campos en vez de 1.

Portar una subclase paralela de ``ResConfigSettings`` aquí, sin que
``base_setup`` (o cualquier otro controller) la lea, produciría un
formulario sin lector — exactamente el "relleno" que
``auto-audit-before-writing.md`` prohíbe (sección "Lo que no escribo").
Mismo criterio, además, que ``account_debit_note.AccountDebitNoteWizard``
fija para sus tres campos de soporte de widget (``move_type``,
``journal_type``, ``country_code``): "sin formulario DRF en este pase".

**DESCONOCIDO declarado, con condición de cierre explícita:** el día que
``base_setup.SiteConfigSettings`` (o un formulario de ajustes de
Contabilidad equivalente) exista y necesite exponer estos 6 campos, el
patrón correcto es añadirlos ahí con ``field_attrs={'related_company_field':
'check_printing_settings.<campo>'}`` (o el mecanismo que ese formulario use
para escribir en un modelo satélite) — no crear una segunda clase
``ResConfigSettings`` paralela.

El dato SIGUE completo — sólo falta el formulario
========================================================

Ningún dato se pierde: los 6 campos están en
``CheckPrintingCompanySettings`` (``models/res_company.py``), leíbles y
escribibles por cualquier consumidor (DRF view futura, management command,
shell). Lo único ausente es el FORMULARIO de ajustes que los expondría en
el cliente web — capa que este árbol headless no tiene para NINGÚN addon
salvo ``base_setup``.
"""
