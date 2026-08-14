# Adaptado de Odoo Community `odoo/addons/base/__manifest__.py` (LGPL-3) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Núcleo (base)',
    'version': '1.0',
    'category': 'Hidden',
    'summary': (
        'El addon del que depende el árbol entero: ResCompany, ResPartner, '
        'ResUsers, ResCurrency, ResCountry, ir.model.*, ir.cron, ir.rule, '
        'ir.ui.view, SystemParameter, DecimalPrecision y los mixins'
    ),
    # `depends` VACÍO, igual que la referencia: `base` es la raíz del grafo y
    # no declara ninguna dependencia (medido en
    # `odoo19c: odoo/addons/base/__manifest__.py` — no tiene clave `depends`).
    #
    # El `depends` MEDIDO de este addon da ['authz'], por tres sitios:
    # `authz_catalog.py:25` y `management/commands/update_module_list.py:54`
    # importan `addons.authz.declaration`; `models/ir_ui_menu.py:290` nombra
    # la constante 'authz.Capability'. Declararlo aquí legitimaría un ciclo
    # `base ↔ authz` que atrapa 89 de los 91 addons y deja el grafo sin orden
    # topológico — ver H-API-562, sucesor tarea #322.
    #
    # En la referencia el control de acceso (`ir.model.access`, `res.groups`)
    # vive DENTRO de `base`, así que allí la arista no existe. Dónde debe vivir
    # aquí el mecanismo de declaración de capacidades es la decisión que #322
    # tiene que medir; hasta entonces la raíz se declara raíz.
    'depends': [],
    # Licencia de la fuente de la que se adapta este addon, tal como su manifest
    # la declara (DEC-KX-03 punto 1): `base` en Odoo Community es LGPL-3.
    'license': 'LGPL-3',
    'application': False,  # núcleo técnico, no módulo vendible
    'installable': True,
    'auto_install': True,  # sin `base` no arranca nada
}
