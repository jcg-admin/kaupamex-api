"""Modelos del addon ``base_install_request``.

**Deliberadamente vacío de imports.** ``BaseInstallRequestConfig.ready()``
importa ``ir_module_module`` y aplica su extensión; en tiempo de import del
paquete el registro de modelos aún no está poblado y colgar sobre
``base.IrModule`` fallaría con ``AppRegistryNotReady``. Mismo criterio que
``addons.base_iban.models``.

Mapa de porte por archivo de la referencia:

- ``models/ir_module_module.py`` → ``ir_module_module.py`` (1 de 1 símbolo).
- ``wizard/base_module_install_request.py`` → ``base_module_install_request.py``
  (bloqueo medido, ver su docstring).
"""
