"""Addon ``html_builder`` — el constructor de páginas, sin lado de servidor.

Puerto de Odoo Community ``html_builder/`` (``odoo19c:``, LGPL-3 — copia +
adaptación con atribución, DEC-KX-03).

Su ``__init__.py`` de la referencia está **vacío**, y no es una casualidad
que haya que explicar: **este addon no tiene lado de Python**. Medido sobre la
fuente, sus dos únicos archivos ``.py`` fuera de ``tests/`` son este
``__init__.py`` vacío y el ``__manifest__.py``, cuyas 70 líneas son en su
práctica totalidad declaraciones de *bundles* de JS y SCSS.

Así que el porte de este addon es exactamente **el paquete**: su ``apps.py`` y
su manifiesto con el ``depends`` medido. No hay símbolos que portar, y decirlo
con esta precisión es lo que distingue *"no tiene nada"* de *"no se portó"*.

Dónde vive lo que este addon aporta
====================================

En ``kaupamex-ui``. El constructor es un componente de React: la fuente lo
declara como recursos —``html_builder/static/src/**``— y ese empaquetado lo
hace webpack en el repositorio de UI, no Django. Un bloque ``assets`` aquí
declararía rutas a archivos que este repositorio no tiene.

Por qué el paquete existe igualmente
=====================================

Tres cosas de este árbol lo consumen, y las tres son de servidor:

1. ``html_editor.controllers.main.shape`` traduce el módulo histórico
   ``web_editor`` a ``html_builder`` para servir sus formas SVG
   (``odoo19c: html_editor/controllers/main.py:578-579``), así que el nombre
   del addon es parte de una ruta viva.
2. El grafo de ``depends`` deriva ``INSTALLED_APPS``
   (``src/config/settings/base.py``, ``_local_apps()``): sin manifiesto, el
   addon no puede ser dependencia declarada de nadie.
3. ``ir.module.module`` puebla su catálogo técnico de los manifiestos; un
   addon sin el suyo es estado que el sistema no registra en ninguna parte.
"""
