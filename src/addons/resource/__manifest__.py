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
        'base',      # TimeStampedModel, ResCompany, ResUsers
    ],
    # Licencia de la fuente de la que se adapta este addon, tal como su
    # manifest la declara (DEC-KX-03 punto 1): `resource` en Odoo Community
    # es LGPL-3.
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
