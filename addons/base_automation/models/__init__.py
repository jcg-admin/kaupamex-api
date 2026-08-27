from .base_automation import BaseAutomation, BaseAutomationAction  # noqa: F401

# ir_actions_server.py NO se importa aquí: instala chain_method() como
# efecto de importación (excepción #4 de no-lazy-imports), y sólo debe
# ejecutarse una vez, desde BaseAutomationConfig.ready() — importarlo
# también aquí (en tiempo de carga del paquete de modelos) lo correría
# antes de que el registro de apps esté listo. Ver apps.py.
