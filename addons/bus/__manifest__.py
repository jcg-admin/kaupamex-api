# Adaptado de Odoo Community `bus/__manifest__.py` (LGPL-3, odoo19c:) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Bus de mensajes',
    'version': '1.0',
    'category': 'Hidden',
    'summary': (
        'BusMessage y BusListenerMixin: el canal por el que un modelo notifica '
        'a un destinatario sin acoplarse a él'
    ),
    # `depends` MEDIDO contra los imports reales. La referencia declara
    # ['base', 'web']; `web` aporta el cliente JS del long-polling, que aquí
    # no aplica: el consumidor del bus es el repo `ui` por HTTP.
    #
    # La arista medida `bus → authz` no se declara, por el mismo criterio que
    # `base_setup`: el gate de capacidad no es dependencia de datos.
    'depends': [
        'base',  # ResUsers, ResCompany, los mixins
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
