"""Configuración experimental de un proceso; no settings productivos ni cambio por request."""
import os
from config.settings.testing import *
from modules.module_graph import ModuleGraph
from modules.module import get_modules

PROBE_MODULES = frozenset(os.environ['ORM_PROBE_MODULES'].split(','))
if os.environ.get('ORM_PROBE_RESOLVE_DEPENDENCIES') == '1':
    available = ModuleGraph()
    available.extend(get_modules())
    closure = ModuleGraph()
    closure.extend(tuple(PROBE_MODULES))
    while True:
        selected = {node.name for node in closure}
        automatic = set(available.auto_installable(selected)) - selected
        if not automatic:
            break
        closure.extend(tuple(automatic))
    PROBE_MODULES = frozenset(selected)
INSTALLED_APPS = tuple(app for app in INSTALLED_APPS
                       if not app.startswith('addons.') or app.split('.')[1] in PROBE_MODULES)
