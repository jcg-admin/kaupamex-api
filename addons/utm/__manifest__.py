# Adaptado de Odoo Community `utm/__manifest__.py` (LGPL-3) — atribución y
# aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Rastreadores UTM (campaña, medio, fuente)',
    'version': '1.1',
    'category': 'Marketing',
    'summary': (
        'utm.{campaign,medium,source,stage,tag} + utm.mixin + utm.source.mixin'
        ' — los tres ejes UTM y su captura por cookie'
    ),
    # `depends` MEDIDO contra los imports reales de los modelos de este addon.
    # La referencia declara `['base', 'web']`; `web` allá aporta los assets del
    # cliente (`utm/static/src/**`), que este monolito no tiene. Se conserva
    # `base` —de donde salen `IrHttp`, `IrModelData`, `ResUsers` y
    # `TimeStampedModel`— y se omite `web` con esa razón declarada.
    'depends': [
        'base',  # IrHttp, IrModelData, ResUsers, TimeStampedModel
    ],
    # Licencia de la fuente de la que se adapta este addon, tal como su
    # manifest
    # la declara (DEC-KX-03 punto 1): `utm` en Odoo Community es LGPL-3.
    'license': 'LGPL-3',
    # Seguridad de la fuente (``odoo19c: utm/__manifest__.py:23``), por
    # ``load_data`` en el ciclo de instalación: copia fiel del CSV. Los cuatro
    # ``data/*.xml`` siguen sembrándose desde ``addons.utm.data`` (la unidad
    # ``record-loader-universality-0485`` los lleva a este mismo camino) y las
    # vistas no se cargan: este árbol no sirve el cliente web.
    'data': [
        'security/ir.model.access.csv',
    ],
    'application': False,
    'installable': True,
    'auto_install': False,
}
