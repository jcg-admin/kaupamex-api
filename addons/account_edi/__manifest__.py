# Adaptado de Odoo Community `account_edi/__manifest__.py` (LGPL-3) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Import/Export Invoices From XML/PDF',
    'version': '1.0',
    'category': 'Accounting/Accounting',
    'summary': (
        'account.edi.format + account.edi.document — el registro genérico '
        'de formatos de facturación electrónica y el ciclo de vida de sus '
        'documentos por asiento'
    ),
    # `depends` MEDIDO contra los imports reales de los modelos de este
    # addon. La referencia declara sólo `['account']`; aquí es lo mismo —
    # `base` llega transitivamente vía `account`.
    'depends': [
        # AccountMove, AccountJournal, AccountMoveSend, IrAttachment
        'account',
    ],
    # Licencia de la fuente de la que se adapta este addon, tal como su
    # manifest la declara (DEC-KX-03 punto 1): `account_edi` en Odoo
    # Community es LGPL-3.
    'license': 'LGPL-3',
    'application': False,
    # Seguridad de la fuente
    # (``odoo19c: addons/account_edi/__manifest__.py:17``): copia fiel del CSV.
    # Las vistas de la fuente no se cargan aquí; su cron
    # (``data/cron.xml``) lo siembra la migración
    # ``0007_seed_cron_edi_network``.
    'data': [
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'auto_install': False,
}
