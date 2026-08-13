# Adaptado de Odoo Community `sale/__manifest__.py` (LGPL-3) — atribución y
# aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Pedidos',
    'version': '1.0',
    'category': 'Order Management',
    'summary': 'La venta ES la orden: cotización, confirmación y su recorrido',
    # `depends` MEDIDO contra los imports reales (`from addons.<x>` en
    # src/addons/sale), no copiado de la referencia: allí son
    # ['sales_team', 'account_payment', 'utm'] porque su `sale` es más delgado
    # —el nuestro absorbió `catalogue`/`inventory` al disolverlos.
    #
    # Antes decía ['catalogue', 'inventory']: DOS addons que ya NO EXISTEN
    # (se disolvieron en `product` y `stock`). El grafo de `modules/` lo
    # destapó en su primera ejecución — ver H-API-229.
    #
    # TERCERA ocurrencia del mismo defecto: `company` tampoco existe ya (se
    # disolvió en `base`, #19/#35) y siguió declarado hasta que la
    # calibración de `derivar_depends.py` lo midió. Los tres se declararon
    # correctos en su momento y sobrevivieron a la disolución del addon: un
    # `depends` no se invalida solo cuando su destino desaparece.
    'depends': [
        'account',
        'authz',
        'base',
        'delivery',
        'loyalty',
        'mail',
        'observability',
        'payment',
        'sales_team',
        'stock',
    ],
    # NO se declara `sale_loyalty`: `sale` lo importa (1 archivo) pero en la
    # referencia la dirección es la contraria —`sale_loyalty` depende de
    # `sale`—. Declararlo aquí legitimaría la inversión en vez de registrarla;
    # el gate de dirección (`scripts/check_addon_cycles.py`) es su dueño.
    #
    # Declaración de la licencia de la fuente de la que se adapta este addon,
    # tal como su manifest la declara (DEC-KX-03 punto 1): una licencia NO se
    # re-etiqueta. Aquí es la de `sale` en Odoo Community.
    'license': 'LGPL-3',
    # `application` de Odoo: módulo vendible, no técnico. Alimenta
    # `authz.Module.is_application`.
    'application': True,
    'installable': True,
    'auto_install': False,
}
