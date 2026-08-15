# Adaptado de Odoo Community `rpc/__manifest__.py` (LGPL-3) — atribución y
# aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Despacho genérico por modelo y método',
    'version': '1.0',
    'category': 'Extra Tools',
    'summary': 'POST /json/2/<model>/<method> — el endpoint programático a los modelos',
    # `depends` MEDIDO contra los imports reales de este addon: `base` aporta el
    # registro por nombre (`orm.registry`) y `authz` el segundo gate
    # (`HasCapability`). La referencia declara sólo `["base"]` porque allá el
    # control de acceso vive en el ORM, no en la vista.
    'depends': ['base', 'authz'],
    'author': 'Equipo Kaupamex',
    'license': 'LGPL-3',
    # La referencia lo declara `auto_install: True` — el despacho programático
    # es parte del producto, no un extra. Aquí el equivalente es estar en
    # INSTALLED_APPS, que `_local_apps()` deriva del grafo de `depends`.
}
