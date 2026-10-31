"""Anulación sólo en memoria: el verificador debe detectar no leer el snapshot."""
from pathlib import Path
import runpy
from unittest.mock import patch

import django

django.setup()

from modules.module_graph import ModuleGraph

with patch.object(ModuleGraph, '_update_from_database', lambda *args, **kwargs: None):
    runpy.run_path(str(Path(__file__).with_name('verify_snapshot_contract.py')), run_name='__main__')
