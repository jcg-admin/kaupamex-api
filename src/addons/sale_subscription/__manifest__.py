{
    'name': 'Suscripciones (billing recurrente L0)',
    'summary': 'Suscripción de módulos por compañía, corridas de cobro y '
               'facturas de suscripción del operador de plataforma.',
    # Reimplementación NATIVA del patrón de `sale_subscription` de Odoo 19
    # Enterprise (OEEL-1 → no se copia código, DEC-KX-03): allá el addon
    # extiende sale.order / account.move / product.pricelist por `_inherit`
    # y aporta sus modelos propios (plan, log, close_reason). Aquí el eje de
    # negocio es propio (suscripción de MÓDULOS por compañía, DEC-KX-05) y
    # los modelos son propios: ModulePrice, CompanyModuleSubscription,
    # SubscriptionBillingRun, SubscriptionInvoice (asienta en
    # account.AccountMove, H-API-244). Ver analisis-disolucion-platform.
    'depends': [
        'base',     # ResCompany (la compañía suscrita) + extensión _inherit
        'authz',    # Module (el catálogo de módulos suscribibles)
        'account',  # AccountMove (el libro donde asienta SubscriptionInvoice)
    ],
    # Eje plataforma-propia: no adapta un addon concreto de la referencia,
    # reimplementa su patrón. Sin licencia heredada que declarar.
    'license': 'propio',
}
