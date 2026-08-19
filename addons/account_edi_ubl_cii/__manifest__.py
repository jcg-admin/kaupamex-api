# Adaptado de Odoo Community `account_edi_ubl_cii/__manifest__.py` (LGPL-3) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': "Import/Export electronic invoices with UBL/CII",
    'version': '1.0',
    'category': 'Accounting/Accounting',
    'description': """
Electronic invoicing module
===========================

Allows to export and import formats: E-FFF, UBL Bis 3, EHF3, NLCIUS,
Factur-X (CII), XRechnung (UBL). When generating the PDF on the invoice, the
PDF will be embedded inside the xml for all UBL formats. This allows the
receiver to retrieve the PDF with only the xml file. Note that **EHF3 is fully
implemented by UBL Bis 3**.

The formats can be chosen from the journal (Journal > Advanced Settings)
linked to the invoice.

Note that E-FFF, NLCIUS and XRechnung (UBL) are only available for Belgian,
Dutch and German companies, respectively. UBL Bis 3 is only available for
companies which country is present in the EAS list.
    """,
    # `depends` MEDIDO contra los imports reales de este addon:
    #   addons.account.tools                        -> dict_to_xml
    #   addons.account.models.account_move          -> AccountMove
    #   addons.account.models.account_tax           -> AccountTax
    #   addons.account.models.account_move_send     -> AccountMoveSend
    #   addons.account.wizard.account_move_send_wizard -> AccountMoveSendWizard
    #   addons.base.models.res_partner              -> ResPartner
    #   addons.base.models.ir_actions_report        -> IrActionsReport
    # Coincide con la referencia (`['account']`); `base` llega transitivamente
    # vía `account`, igual que en `account_edi/__manifest__.py`.
    'depends': [
        'account',
    ],
    # `data` de la referencia (plantillas QWeb de CII/UBL 2.0, vistas de
    # account.tax / account.move / res.partner, y el reporte) NO se porta: este
    # árbol no tiene motor QWeb ni cargador de vistas XML — mismo desenlace, y
    # por la misma razón, que el resto de los addons ya portados. Los formatos
    # se generan aquí desde Python (`dict_to_xml` + las plantillas de orden de
    # `tools/`), que es el camino que la propia referencia usa en 19 para UBL.
    #
    # `assets` (SCSS de `web.assets_backend`) tampoco: no hay bundle de
    # assets en este árbol.
    #
    # `uninstall_hook` no se porta — ver el docstring de `__init__.py` para las
    # dos piezas ausentes que lo bloquean.
    'installable': True,
    'auto_install': True,
    'application': False,
    'author': 'Odoo S.A.',
    # Licencia de la fuente de la que se adapta este addon, tal como su
    # manifest la declara (DEC-KX-03 punto 1).
    'license': 'LGPL-3',
}
