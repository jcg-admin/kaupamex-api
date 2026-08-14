# Adaptado de Odoo Community `account/__manifest__.py` (LGPL-3, odoo19c:) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Contabilidad y facturación',
    'version': '1.0',
    'category': 'Accounting/Accounting',
    'summary': (
        'El libro: AccountMove y sus líneas, plan de cuentas, diarios, '
        'impuestos, divisa, extracto bancario y plazos de pago'
    ),
    # `depends` MEDIDO contra los imports reales, no copiado de la referencia,
    # que declara ['base_setup', 'onboarding', 'product', 'analytic',
    # 'portal', 'digest'] — seis, de los que aquí sólo `product` se mide:
    #
    #   base_setup  la UI de ajustes; aquí es SystemParameter de `base`.
    #   onboarding  el asistente de alta contable; portado como addon propio,
    #               y es él quien importa a `account`, no al revés.
    #   analytic    la distribución analítica cuelga de la línea de asiento
    #               por FK declarada en `analytic`, esa es la dirección.
    #   portal      la vista de cliente de la factura; vive en `portal`.
    #   digest      el resumen periódico; lo consume, no lo provee.
    #
    # La arista medida hacia `authz` es el gate de capacidad de las vistas
    # DRF (DEC-11), no dependencia de datos — no se declara (ver lote 2).
    'depends': [
        'base',     # ResCompany, ResPartner, ResCurrency, ResBank, SystemParameter
        'product',  # Product y su UoM — la línea de factura factura un producto
        'uom',      # Uom — la cantidad de la línea lleva su unidad
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': True,   # módulo vendible del catálogo L0
    'installable': True,
    'auto_install': False,
}
