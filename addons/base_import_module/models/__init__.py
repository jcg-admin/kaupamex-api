"""Modelos del addon ``base_import_module``.

- ``base_import_module.py`` → ``BaseImportModule``, el asistente (9 de 11
  símbolos; los dos bloqueados llevan su medición y su sucesor en su
  docstring).

Los otros cuatro archivos de la referencia — el contador y su razón
====================================================================

Porte BLOQUEADO — 0 de 30 símbolos

Cuatro archivos que **extienden modelos ajenos**, y los cuatro necesitan un
método previo que este árbol no declara. Medido 2026-09-02:

.. code-block:: text

   grep -cE "def _get_translations_for_webclient" src/addons/base/models/ir_http.py     -> 0
   grep -rnE "def _validate_custom_views|def _check_xml" --include=*.py src/ | wc -l  -> 0
   grep -rnE "class BaseModuleUninstall" --include=*.py src/ addons/ | wc -l            -> 0
   grep -rnE "def _import_zipfile|def _get_missing_dependencies_modules" \
       --include=*.py src/ addons/ | grep -v base_import_module | wc -l               -> 0
   grep -nE "imported|module_type" src/addons/base/models/ir_module.py \
       | grep "fields." | wc -l                                                       -> 0

``orm.method_chain.wrap_method`` **rehúsa** cuando no hay implementación
previa, y con razón: *"super() sobre un método que la base no declara es un
error en la fuente también"*. Los cuatro caen ahí.

- ``models/ir_module.py`` (``IrModuleModule``, **27 símbolos**, 755 líneas) —
  BLOQUEADO por ``ir.module.module.imported`` — el campo que todo el archivo
  lee no existe (medido arriba: 0 declaraciones), porque describe un módulo
  instalado en caliente. El veredicto es de
  ``src/addons/base/models/ir_module.py``, no de este pase: *"Registrar un
  estado que nadie puede alcanzar sería inventar una capacidad."* Sucesor:
  tarea **#452**.
- ``models/ir_http.py`` (``IrHttp._get_translations_for_webclient``, 1) —
  BLOQUEADO por ``ir.http._get_translations_for_webclient`` — la clase existe
  (``src/addons/base/models/ir_http.py:194``) y el método no. Sucesor: tarea
  **#452**.
- ``models/ir_ui_view.py`` (``IrUiView._validate_custom_views``, 1) —
  BLOQUEADO por ``ir.ui.view._check_xml`` — 0 definiciones en ``src/``; la
  extensión valida vistas QWeb importadas contra ``ir_model_data``. Sucesor:
  tarea **#452**.
- ``wizard/base_module_uninstall.py`` (``BaseModuleUninstall._modules_to_display``,
  1) — BLOQUEADO por ``base.module.uninstall`` — el ``TransientModel`` que la
  extensión hereda no existe (0 clases). Sucesor: tarea **#452**.

Fuera de ese conteo: ``controllers/main.py``
(``ImportModule.login_upload``), un endpoint ``auth='none'`` con
usuario/contraseña en el cuerpo — superado por ``authz`` (JWT), que es como
este árbol resuelve autenticación.

Por qué no se crean los cuatro archivos vacíos
===============================================

Un archivo con sólo un docstring de veredicto no añade trazabilidad sobre lo
que este contador ya cubre, y multiplicaría por cuatro el mismo texto. El
sitio de cada uno queda nombrado arriba, que es lo que hace recorrible la
arista ``bloqueado -> bloqueador``.
"""
from addons.base_import_module.models.base_import_module import BaseImportModule

__all__ = ['BaseImportModule']
