# Adaptado de Odoo `base_import/__manifest__.py` (LGPL-3,
# odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de, odoo19c:) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Importación de archivos',
    'version': '2.0',
    'category': 'Hidden/Tools',
    'summary': 'Lee un archivo de datos del usuario, propone el mapeo de '
               'columnas a campos y carga los registros.',
    # `depends` de la referencia: ['web']. Aquí se declara 'base' porque el
    # addon `web` de la referencia es su cliente JS, y la parte que este
    # porte cubre —heurísticas de inferencia y lectura de archivo— no lo
    # necesita. Cuando entre la mitad de UI, esta línea se revisa.
    'depends': [
        'base',
    ],
    # Licencia de la fuente, tal como su manifest la declara (DEC-KX-03
    # punto 1): `base_import` es LGPL-3.
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    # La referencia declara `auto_install: True` — se instala sola en cuanto
    # `web` está presente. Aquí la instalación es `INSTALLED_APPS` y no hay
    # mecanismo de auto-instalación por dependencias, así que queda en False
    # explícito, mismo criterio que `base_sparse_field` y `base_iban`.
    'auto_install': False,
}
