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
    # 'portal', 'digest'] — seis, de los que aquí se miden `product` y
    # `analytic`:
    #
    #   base_setup  la UI de ajustes; aquí es SystemParameter de `base`.
    #   portal      la vista de cliente de la factura; vive en `portal`.
    #   digest      el resumen periódico; lo consume, no lo provee.
    #
    # `analytic` se AÑADIÓ el 2026-08-18: hasta entonces la única arista era
    # una FK declarada del lado de `analytic`, esa dirección, y por eso no se
    # declaraba. Al portar el bloque analítico (H-API-688) aparecieron **seis**
    # llamadas de `chain_method` sobre símbolos cuyo dueño es `analytic`
    # (`_get_default_search_domain_vals`, `_create_domain`,
    # `_get_applicable_models`, `save`, `clean`, `_get_score`), y eso SÍ es
    # dependencia de orden: si el dueño corre su `ready()` después, su
    # `setattr` sepulta la cadena sin avisar. Lo atrapó
    # `check_chain_method_depends` en el pre-commit, no una relectura.
    #
    # La arista medida hacia `authz` es el gate de capacidad de las vistas
    # DRF (DEC-11), no dependencia de datos — no se declara (ver lote 2).
    'depends': [
        'base',      # ResCompany, ResPartner, ResCurrency, ResBank, SystemParameter
        'product',   # Product y su UoM — la línea de factura factura un producto
        'uom',       # Uom — la cantidad de la línea lleva su unidad
        'analytic',  # AccountAnalyticLine/Plan/DistributionModel — 6 chain_method
        # `onboarding` se AÑADIÓ el 2026-08-19 (tanda #75/#398 tramo 3): hasta
        # entonces la única arista era onboarding→account y por eso no se
        # declaraba; al portar account/models/onboarding_onboarding{,_step}.py
        # (la extensión que la referencia declara en account, no en
        # onboarding) aparecieron 11 chain_method sobre símbolos cuyo dueño es
        # `onboarding`. Lo atrapó check_chain_method_depends en el pre-commit.
        'onboarding',  # OnboardingOnboarding/-Step — 11 chain_method
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': True,   # módulo vendible del catálogo L0
    'installable': True,
    'auto_install': False,
}
