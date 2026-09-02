"""Controladores del addon ``html_editor``.

Puerto de Odoo Community ``html_editor/controllers/`` (``odoo19c:``, LGPL-3).
La referencia tiene un solo archivo, ``main.py``, y aquí también.

``urls.py`` **no tiene contraparte en la referencia** y es deliberado: allá la
ruta se declara con ``@http.route`` sobre el método; aquí la declara el
``URLconf`` de Django. Es la misma pieza en el sitio que este stack le da —
mismo criterio que ``addons/bus/controllers/urls.py``.
"""
from . import main

__all__ = ['main']
