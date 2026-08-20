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
    #
    # CUARTA ocurrencia, y esta vez se retiró en el mismo pase que el addon:
    # `observability` se retiró entero (2026-08-20, #621) y su único consumo
    # aquí era el emisor de `ORDER_CANCELLED`, que el chatter ya registraba
    # por duplicado. Ver :ref:`h-api-754`.
    'depends': [
        'account',
        'authz',
        'base',
        'loyalty',
        'mail',
        'payment',
        'sales_team',
        'stock',
    ],
    # NO se declara `sale_loyalty`: `sale` lo importa (1 archivo) pero en la
    # referencia la dirección es la contraria —`sale_loyalty` depende de
    # `sale`—. Declararlo aquí legitimaría la inversión en vez de registrarla;
    # el gate de dirección (`scripts/check_addon_cycles.py`) es su dueño.
    #
    # `delivery` se RETIRÓ por la misma razón (2026-08-13, tarea #296). La
    # referencia declara `delivery → sale` y NO la vuelta
    # (`odoo19c: sale/__manifest__.py` → ['sales_team', 'account_payment',
    # 'utm']), así que declararla aquí cerraba un 2-ciclo `sale ↔ delivery`
    # que dejaba 20 addons sin orden topológico y hacía reventar a
    # `ModuleGraph` con RecursionError. Los cinco sitios que producen la
    # arista medida quedan registrados, no legitimados:
    #   controllers/serializers.py:20 · services.py:26 · amounts.py:29
    #   models/sale_order.py:185 (FK por cadena) · status_projection.py:27
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
