"""Models — ``addons.auto_backup``.

Layout ``models/`` con un archivo por modelo, espejo de la referencia
(``app_auto_backup/models/``, LGPL-3). Este ``__init__`` re-exporta la
superficie pública: ``from addons.auto_backup.models import BackupRecord``
sigue siendo la forma de importar.
"""
from addons.auto_backup.models.backup_record import BackupRecord

__all__ = ['BackupRecord']
