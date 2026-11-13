# Adaptado de Odoo Community `resource/__manifest__.py` (LGPL-3) — atribución
# y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Recursos (calendarios de trabajo, ausencias y disponibilidad)',
    'version': '1.0',
    'category': 'Hidden',
    'summary': (
        'resource.calendar + resource.calendar.attendance + '
        'resource.calendar.leaves + resource.resource + resource.mixin '
        '(abstracto) — motor de intervalos fecha/hora DEFERIDO por falta '
        'de consumidor (ver analisis-familia-resource)'
    ),
    # `depends` MEDIDO contra los imports reales de los modelos portados:
    # sólo TimeStampedModel/ResCompany/ResUsers de `base`. La referencia
    # también depende de `web` (widget JS de sección del calendario) — no
    # aplica (Django+DRF, sin vistas XML de Odoo).
    'depends': [
        'base',  # TimeStampedModel, ResCompany, ResUsers
    ],
    # Licencia de la fuente de la que se adapta este addon, tal como su
    # manifest la declara (DEC-KX-03 punto 1): `resource` en Odoo Community
    # es LGPL-3.
    'license': 'LGPL-3',
    # Seguridad de la fuente (``odoo19c: resource/__manifest__.py:19-20``),
    # por ``load_data`` en el ciclo de instalación y en el mismo orden: copia
    # fiel de los dos archivos. ``data/resource_data.xml`` es la unidad
    # ``resource-data-0397`` (depende de ``base.main_company``); las vistas
    # no se cargan: este árbol no sirve el cliente web.
    'data': [
        'security/ir.model.access.csv',
        'security/resource_security.xml',
    ],
    'application': False,
    'installable': True,
    'auto_install': False,
}
