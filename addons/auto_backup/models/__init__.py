"""Models — ``addons.auto_backup``.

Layout ``models/`` con un archivo por modelo, espejo de la referencia
(``app_auto_backup/models/``, LGPL-3): ``db_backup.py`` (la configuración)
y ``db_backup_details.py`` (cada corrida). Este ``__init__`` re-exporta la
superficie pública.
"""
from addons.auto_backup.models.db_backup import DbBackup
from addons.auto_backup.models.db_backup_details import DbBackupDetails

__all__ = ['DbBackup', 'DbBackupDetails']
