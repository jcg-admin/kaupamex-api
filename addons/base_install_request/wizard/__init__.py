"""Asistentes de ``base_install_request`` — ≙ ``odoo19c: …/wizard/``.

Dos ``TransientModel``: pedir la activación de un módulo y revisarla. El
paquete se llama ``wizard`` porque así lo llama la referencia — el sitio del
archivo es parte del porte (``atributos-de-clase-de-modelo.md`` §2).
"""
from addons.base_install_request.wizard.base_module_install_request import (
    BaseModuleInstallRequest, BaseModuleInstallReview)

__all__ = ['BaseModuleInstallRequest', 'BaseModuleInstallReview']
