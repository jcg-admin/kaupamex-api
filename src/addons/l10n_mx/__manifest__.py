# Adaptado de Odoo Community `l10n_mx/__manifest__.py` (LGPL-3) — atribución y
# aviso de licencia preservados (DEC-KX-03).
{
    'name': 'México — contabilidad',
    'version': '1.0',
    'category': 'Accounting/Localizations/Account Charts',
    'summary': 'Plan de cuentas, impuestos y catálogos fiscales de México',
    # `depends` MEDIDO contra los imports reales de este addon, no copiado de
    # la referencia (que declara sólo `account` porque su ORM resuelve `base`
    # de forma implícita). Aquí los dos son imports de Python explícitos:
    #
    #   account → ChartTemplate, AccountAccount, AccountTax, AccountTaxGroup
    #   base    → ResBank, ResPartnerBank, ResCompany
    'depends': [
        'account',
        'base',
    ],
    # Licencia de la fuente de la que se adapta este addon, tal como su
    # manifest la declara (DEC-KX-03 punto 1): `l10n_mx` en Odoo Community es
    # LGPL-3 — es el ÚNICO de los 19 `l10n_mx*` que se copia. Los otros 17 son
    # OEEL-1 y exigen reimplementación nativa (ver :ref:`h-api-357`).
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
