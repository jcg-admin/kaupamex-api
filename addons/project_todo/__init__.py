"""``project_todo`` — el to-do: una tarea privada, fuera de todo proyecto.

Adaptación de Odoo ``project_todo`` (``odoo19c: addons/project_todo/``,
licencia ``LGPL-3`` declarada en su ``__manifest__.py``) — atribución y aviso
de licencia preservados (DEC-KX-03).

Qué es: la app «To-Do» de Odoo. No inventa un modelo nuevo — un to-do **es**
una ``project.task`` sin proyecto —, así que el addon aporta dos cosas: que
una tarea creada sin nombre tome el suyo de la primera línea de su
descripción, y el asistente que crea de una vez el to-do y la actividad que
lo recuerda.

Layout — contra el de la referencia
=====================================

La referencia trae ``models/``, ``wizard/``, ``data/``, ``security/``,
``views/``, ``static/``, ``i18n/`` y ``tests/``. Aquí:

- ``models/`` — se porta. Ningún modelo propio: ``project_task.py`` cuelga
  de ``project.ProjectTask`` desde ``ready()``; ``res_users.py`` es
  documentación (sus 3 símbolos, bloqueados y medidos — ver su docstring).
- ``wizard/`` — se porta (``mail.activity.todo.create`` → ``TransientModel``
  sin tabla, ≙ ``account_debit_note.AccountDebitNoteWizard``).
- ``data/todo_template.xml`` — **no se porta**: plantilla QWeb del editor web
  (checklists, imágenes embebidas). El compilador de QWeb no existe en este
  árbol y lo declara él mismo
  (``src/addons/base/models/ir_template_expressions.py:261`` levanta ``NotImplementedError``).
- ``security/`` (``ir.model.access.csv`` + ``project_todo_security.xml``) —
  **no se porta**: la referencia sólo declara acceso a la tabla del asistente
  (que aquí no tiene tabla, ``managed = False``) y una regla de registro
  sobre las tareas privadas del usuario. La autorización de este árbol es por
  capacidad (``addons/authz``, ``HasCapability``), no por ACL de modelo;
  cuando exista el endpoint DRF del to-do, la regla se expresa allí. Mismo
  criterio que ``account_debit_note/security/__init__.py``.
- ``views/`` (2 XML) y ``static/`` — **no se portan**: cliente web de Odoo
  (el de este proyecto es React). Con ellos cae ``get_todo_views_id``, que
  sólo resuelve sus identificadores externos.
- ``i18n/`` y ``tests/`` — los ``.po`` son del harness de Odoo; en este árbol
  los tests unitarios viven fuera del addon, en ``tests/unit/``.

``post_init_hook`` — declarado y no portado
==============================================

La referencia declara ``'post_init_hook': '_todo_post_init'``
(``odoo19c: addons/project_todo/__init__.py:5-6`` y ``__manifest__.py:24``):
al instalar, siembra el to-do de bienvenida a todos los usuarios internos.
No se porta, y no por pereza: su cuerpo llama a
``_generate_onboarding_todo``, bloqueado por el compilador de QWeb (medido,
ver ``models/res_users.py``), y filtra con ``search([("share", "=", False)])``
sobre ``share``, que aquí es una ``property`` calculada
(``src/addons/base/models/res_users.py:645``) y no una columna por la que el
ORM pueda filtrar. Django tampoco tiene ``post_init_hook``: el precedente del
árbol es expresarlo como migración de datos
(``account_check_printing/migrations/0002_seed_check_payment_method.py``), y
las migraciones no son de este pase.

Este archivo NO importa ``models`` — el patrón local (``addons/utm``,
``addons/project_account``) deja el ``__init__.py`` raíz sin imports; la
extensión corre en ``ProjectTodoConfig.ready()``.
"""
