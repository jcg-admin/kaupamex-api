# Adaptado de Odoo Community `html_editor/__manifest__.py` (LGPL-3, odoo19c:) —
# atribución y aviso de licencia preservados (DEC-KX-03). La licencia se leyó
# del manifiesto de la fuente, no de la reputación del árbol:
#   grep -oP "'license'\s*:\s*'\K[^']+" $ODOO19C/addons/html_editor/__manifest__.py
# Mecanismo que esa licencia habilita: copia + adaptación con atribución.
{
    'name': 'HTML Editor',
    'version': '1.0',
    'category': 'Hidden',
    'summary': (
        'La mitad de servidor del editor de contenido: guardar lo editado, '
        'el historial de revisiones de un campo HTML, los adjuntos de imagen '
        'y el canal de coedición'
    ),
    'description': """
Html Editor
==========================
This addon provides an extensible, maintainable editor.
    """,
    # `depends` MEDIDO contra los imports reales de este addon, y coincide con
    # el de la referencia (`['base', 'bus', 'web']`):
    #
    # - `base`  — IrAttachment, IrHttp, IrUiView, IrTemplateExpressions,
    #             IrFieldConverter*, Base, TimeStampedModel, tools.misc,
    #             tools.json
    # - `bus`   — BusMessage.sendone y la función de módulo
    #             `build_bus_channel_list`, que `models/ir_websocket.py`
    #             envuelve
    # - `web`   — el addon que dueña `ir.binary`/`ir.http` del lado del
    #             cliente y cuyas capacidades de adjunto conviven con las de
    #             este addon; se conserva por fidelidad al `depends` de la
    #             fuente y porque fija el orden de carga frente a `web`
    'depends': [
        'base',
        'bus',
        'web',
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    # La referencia lo declara `auto_install: True` — se instala solo en
    # cuanto sus dependencias están. Aquí `INSTALLED_APPS` se deriva del grafo
    # de manifiestos y no hay estado de instalación por empresa que consultar,
    # así que la clave se conserva por fidelidad al dato de la fuente.
    'auto_install': True,
    # La referencia declara aquí `data: ['security/ir.model.access.csv']`. Su
    # equivalente en este árbol es `security/authz_catalog.py`, que
    # `seed_authz` recolecta por `addons.authz.declaration.discover()` — mismo
    # criterio que `addons/web/security/authz_catalog.py`. No se declara en
    # `data` porque el recolector recorre `INSTALLED_APPS`, no el manifiesto.
    #
    # El bloque `assets` de la referencia —21 bundles de JS y SCSS, que son la
    # mayor parte de su manifiesto— NO tiene contraparte aquí: el editor es un
    # componente de React y vive en `kaupamex-ui`, empaquetado por webpack.
    # Declarar aquí rutas a `html_editor/static/**` sería declarar archivos
    # que este repositorio no tiene.
}
