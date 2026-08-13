# Adaptado de Odoo Community `analytic/__manifest__.py` (LGPL-3) — atribución y
# aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Contabilidad analítica (planes, cuentas, distribución)',
    'version': '1.0',
    'category': 'Accounting/Accounting',
    'summary': (
        'account.analytic.{plan,applicability,account,line,distribution.model} '
        '+ analytic.mixin — sin columnas dinámicas por plan (cierre parcial)'
    ),
    # `depends` MEDIDO contra los imports reales de los modelos de este addon
    # (no copiado de la referencia, que además declara `mail`/`web` como deps
    # de la UI de Studio/vistas que no aplican a este monolito Django).
    'depends': [
        'base',  # ResCompany, ResPartner, ResUsers, ResCurrency, TimeStampedModel,
                 # _reject_hierarchy_cycle, DecimalPrecision
        'mail',  # MailThread — account.analytic.account hereda mail.thread
        'uom',   # Uom — account.analytic.line.product_uom
    ],
    # Licencia de la fuente de la que se adapta este addon, tal como su manifest
    # la declara (DEC-KX-03 punto 1): `analytic` en Odoo Community es LGPL-3.
    'license': 'LGPL-3',
    'application': False,  # corte parcial, no el módulo completo
    'installable': True,
    'auto_install': False,
}
