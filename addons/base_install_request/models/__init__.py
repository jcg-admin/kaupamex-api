"""Modelos del addon ``base_install_request``.

Mapa de porte por archivo de la referencia:

- ``models/ir_module_module.py`` → ``ir_module_module.py`` (1 de 1 símbolo).
- ``wizard/base_module_install_request.py`` → el paquete hermano ``wizard/``
  (6 de 8 símbolos; los dos bloqueados llevan su razón medida y su sucesor).

**El import del asistente NO es decorativo.** Django descubre los modelos de
una app importando su módulo ``models``; los dos ``TransientModel`` viven en
``wizard/``, así que sin esta línea no se registrarían y no tendrían tabla.
Es el mismo camino por el que ``account/models/__init__.py`` importa los suyos.

``ir_module_module`` **no** se importa aquí: cuelga un método sobre
``base.IrModule`` y lo aplica ``BaseInstallRequestConfig.ready()``; en tiempo
de import del paquete el registro de modelos aún no está poblado.
"""
from addons.base_install_request.wizard import (
    BaseModuleInstallRequest, BaseModuleInstallReview)

__all__ = ['BaseModuleInstallRequest', 'BaseModuleInstallReview']
