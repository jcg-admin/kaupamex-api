"""Namespace de addons — UN paquete, DOS directorios. ≙ ``odoo.addons``.

La referencia reparte sus addons en dos raíces y las une en un solo namespace
(``odoo/modules/module.py:initialize_sys_path``)::

    odoo/addons/    base + los 23 test_*     addons_base_dir
    addons/         los 629 restantes        addons_community_dir = dirname(root_path)/addons

Aquí ``src/`` es el paquete que allí es ``odoo/``, así que la comunidad cae en
la raíz del repositorio. El reparto se mide, no se elige: de nuestros 91
addons, ``base`` es el único que la referencia declara en ``odoo/addons/``.

**Por qué esto importa más de lo que parece.** Unir las dos raíces en un solo
``__path__`` es lo que mantiene ``addons.<x>`` como ruta de import
independientemente de en qué disco viva el addon. Sin ello, mover un addon
entre raíces obligaría a reescribir sus imports, sus labels en
``INSTALLED_APPS`` y las etiquetas de sus migraciones — y el reparto dejaría
de ser una decisión de layout para volverse una migración de datos.

El ``append`` corre al importar el paquete: es el momento más temprano
disponible, porque Django resuelve ``addons.<x>`` mientras procesa
``INSTALLED_APPS``, antes de que se ejecute ningún punto de entrada nuestro.
"""
from modules.module import initialize_sys_path

initialize_sys_path(__path__)
