"""AppConfig — ``addons.account_edi_ubl_cii``.

Adaptación del addon ``account_edi_ubl_cii`` de Odoo 19 (LGPL-3): la
importación y exportación de facturas electrónicas en los formatos E-FFF,
UBL Bis 3, EHF3, NLCIUS, Factur-X (CII), XRechnung (UBL), A-NZ y SG.

Este addon **no declara ningún modelo Django propio** (los catorce
constructores son clases Python planas — ver
``models/account_edi_common.py``). Lo que sí aporta a la base de datos son
campos colgados sobre modelos de otros addons, y eso lo aplica ``ready()``:

* ``account.tax`` → ``ubl_cii_tax_category_code``,
  ``ubl_cii_tax_exemption_reason_code`` (+ ``ubl_cii_requires_exemption_reason``
  como ``property``);
* ``account.move`` → ``ubl_cii_xml_file``, ``ubl_cii_xml_id``
  (+ ``ubl_cii_xml_filename`` como ``property``);
* ``res.partner`` → ``peppol_endpoint``, ``peppol_eas`` (+ ``is_ubl_format``,
  ``is_peppol_edi_format`` y ``available_peppol_eas`` como ``property``).

Además cuelga métodos, sin campos, sobre ``account.move.send``,
``account.move.send.wizard`` e ``ir.actions.report``.
"""
import importlib

from django.apps import AppConfig


class AccountEdiUblCiiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.account_edi_ubl_cii'
    label = 'account_edi_ubl_cii'
    verbose_name = 'Facturación electrónica — UBL / CII'

    #: Módulos que extienden modelos de OTRO addon — ≙ ``_inherit``. Cada uno
    #: declara su propia función ``apply_*_extensions()`` (nombre distinto por
    #: módulo, a diferencia de ``account_edi``: aquí el par
    #: ``(módulo, función)`` se declara explícito, que es lo que la regla 11 de
    #: la tanda pide).
    _EXTENSIONS = (
        ('addons.account_edi_ubl_cii.models.account_tax',
         'apply_account_edi_ubl_cii_account_tax_extensions'),
        ('addons.account_edi_ubl_cii.models.res_partner',
         'apply_account_edi_ubl_cii_res_partner_extensions'),
        ('addons.account_edi_ubl_cii.models.account_move',
         'apply_account_edi_ubl_cii_account_move_extensions'),
        ('addons.account_edi_ubl_cii.models.account_move_send',
         'apply_account_edi_ubl_cii_account_move_send_extensions'),
        ('addons.account_edi_ubl_cii.models.ir_actions_report',
         'apply_account_edi_ubl_cii_ir_actions_report_extensions'),
        ('addons.account_edi_ubl_cii.wizard.account_move_send_wizard',
         'apply_account_edi_ubl_cii_send_wizard_extensions'),
    )

    def ready(self):
        """Aplica lo que este addon cuelga de modelos ajenos.

        ``importlib.import_module`` y no un ``import`` al top — excepción #4 de
        ``no-lazy-imports.md``: es una llamada de función, no un statement
        ``import``, así que el gate AST la deja pasar. Mismo patrón que
        ``AccountEdiConfig.ready()``.

        El orden importa en un punto: ``res_partner`` cuelga
        ``_get_ubl_cii_formats_info`` sobre ``ResPartner``, y el asistente de
        envío lo invoca; por eso va antes que ``account_move_send`` y que el
        wizard.
        """
        for module_path, function_name in self._EXTENSIONS:
            getattr(importlib.import_module(module_path), function_name)()
