# Adaptación de `app_auto_backup` (odoo-tools@622ddc2a, 18.x/app-odoo-18.0),
# declarado LGPL-3 por su propio `__manifest__.py` — copia + adaptación con
# atribución (DEC-KX-03).
#
# Este comentario decía lo contrario: *"la referencia Community no tiene addon
# de respaldo — su equivalente es el servicio `db.dump` del propio servidor, y
# el addon `auto_backup` que circula es de la OCA (server-tools), no de Odoo
# S.A."*. Medido, es falso: `app_auto_backup` existe en el corpus y es la
# contraparte real de este addon. Sobre la premisa falsa el addon se quedó sin
# el modelo de configuración (`db.backup`) y con la ejecución renombrada. Ver
# H-API-763.
{
    'name': 'Respaldo programado',
    'version': '1.0',
    'category': 'Hidden/Tools',
    'summary': (
        'db.backup (dónde, cómo y cuánto se conserva) y db.backup.details '
        '(cada corrida con su archivo), con el planificador de 12 horas'
    ),
    # `depends` MEDIDO da ['authz', 'base', 'mail']. Se declaran dos: `authz`
    # es el gate de capacidad de `AdminBackupListView`, no dependencia de
    # datos (mismo criterio que `base_setup`).
    'depends': [
        'base',  # ResCompany, SystemParameter, ir.cron, ir.module.module
        'mail',  # el aviso al operador cuando la copia remota falla
    ],
    # Dependencia externa: `paramiko`, el mismo transporte SFTP que la fuente
    # exige con un `raise ImportError` a nivel de módulo. Se declara en
    # `pyproject.toml` en vez de vendorizarse — el precedente del árbol es
    # `webauthn` (H-API-228).
    'external_dependencies': {'python': ['paramiko']},
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
