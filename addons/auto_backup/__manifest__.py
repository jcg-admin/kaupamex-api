# Forma propia: la referencia Community no tiene addon de respaldo — su
# equivalente es el servicio `db.dump` del propio servidor, y el addon
# `auto_backup` que circula es de la OCA (server-tools), no de Odoo S.A.
{
    'name': 'Respaldo programado',
    'version': '1.0',
    'category': 'Hidden/Tools',
    'summary': (
        'BackupRecord: la corrida de respaldo con su destino, su resultado y '
        'su retención, listable por el operador L0'
    ),
    # `depends` MEDIDO da ['authz', 'base', 'mail']. Se declaran dos: `authz`
    # es el gate de capacidad de `AdminBackupListView`, no dependencia de
    # datos (mismo criterio que `base_setup`).
    'depends': [
        'base',  # ResCompany, SystemParameter (destino y retención)
        'mail',  # el aviso al operador cuando una corrida falla
    ],
    # Eje propio: sin addon de la referencia del que heredar licencia
    # (DEC-KX-03).
    'license': 'propio',
    'application': False,
    'installable': True,
    'auto_install': False,
}
