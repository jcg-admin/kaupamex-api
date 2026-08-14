# Adaptado de Odoo Community `base_setup/__manifest__.py` (LGPL-3, odoo19c:) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Ajustes del sitio',
    'version': '1.0',
    'category': 'Hidden',
    'summary': (
        'SiteConfigSettings: los ajustes del sitio por empresa, expuestos por '
        'DRF — el análogo del `res.config.settings` de la referencia'
    ),
    # `depends` MEDIDO contra los imports reales. La referencia declara
    # ['base', 'web']; `web` es el bundle de assets del panel de ajustes, que
    # este monolito no sirve (la pantalla vive en el repo `ui`).
    #
    # La arista medida `base_setup → authz` NO se declara: `authz` no es una
    # dependencia de datos sino el gate de capacidad que toda vista DRF
    # atraviesa (DEC-11). Declararlo aquí lo volvería dependencia de cada uno
    # de los 91 addons y el `depends` dejaría de decir nada.
    'depends': [
        'base',  # ResCompany, CompanySetting, SystemParameter
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
