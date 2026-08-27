"""``res.users`` extendido por ``project_todo`` — los 3 símbolos, bloqueados.

Adaptación de Odoo ``project_todo/models/res_users.py``
(``odoo19c: addons/project_todo/models/res_users.py``, 115 líneas, LGPL-3)
— atribución y aviso de licencia preservados (DEC-KX-03).

**Este módulo no instala nada** y por eso no exporta ninguna función
``apply_*``: los tres símbolos que la referencia declara están bloqueados por
piezas ausentes y medidas, y ``ProjectTodoConfig._EXTENSIONES`` no lo carga.
Existe para conservar el SITIO del archivo contra la referencia y dejar el
desenlace por símbolo greppeable — mismo criterio que
``account_debit_note/security/__init__.py``. No es un *stub*: no cuelga un
método vacío sobre ``ResUsers`` que sepulte la implementación real el día que
sus bloqueadores caigan (:ref:`h-api-733`).

Porte símbolo por símbolo — 3 símbolos, 3 bloqueados
=====================================================

``_get_activity_groups`` (``:12-89``) — BLOQUEADO en dos niveles
------------------------------------------------------------------

Parte el contador de actividades de la bandeja (*systray*) del cliente web en
dos grupos —«Tarea» y «To-Do»— según la tarea tenga proyecto o no.

1. **No hay base que encadenar.** El método al que la referencia le hace
   ``super()._get_activity_groups()`` vive en ``mail``
   (``odoo19c: addons/mail/models/res_users.py:457``) y **no está portado**:
   medido, ``grep -rn "_get_activity_groups" addons/ src/ --include=*.py``
   → **0 hits**. Sin base, el ``super()`` que quita el grupo
   ``project.task`` de la lista no tiene de dónde quitarlo, y portar esto
   sería inventar el contrato además de la implementación — mismo desenlace
   y misma forma que ``account/models/res_users.py::get_application_groups``.
2. **Sus dos piezas de apoyo tampoco existen** (medido, 0 hits cada una):
   ``ProjectTask._systray_view`` (``odoo19c: project/models/project_task.py:106``)
   y ``modules.Manifest.for_addon`` (``src/modules/module.py`` declara
   ``class Manifest`` pero **no** ``for_addon``), del que la referencia saca
   el icono de cada grupo.

Es además dato de presentación del cliente web de Odoo; este árbol renderiza
en React y no tiene esa bandeja. **Sucesor:** tarea PENDIENTE DE ASIGNAR
(resumen de este pase) — se retoma cuando ``mail`` porte
``res.users._get_activity_groups``.

``_onboard_users_into_project`` (``:91-94``) — BLOQUEADO
----------------------------------------------------------

Es un gancho sobre el método homónimo del addon base ``project``
(``odoo19c: project/models/res_users.py:16``), al que la referencia le hace
``super()`` y del que toma los usuarios recién dados de alta. Medido:
``grep -rn "_onboard_users_into_project" addons/ src/ --include=*.py`` →
**0 hits** — el ``project`` de este árbol no lo porta, así que instalar aquí
el gancho dejaría un método vivo que nadie invoca. Su cuerpo delega en
``_generate_onboarding_todo``, bloqueado más abajo por razones propias.
**Sucesor:** tarea PENDIENTE DE ASIGNAR — mismo pase que porte
``project.res.users._onboard_users_into_project``.

``_generate_onboarding_todo`` (``:96-115``) — BLOQUEADO por el motor QWeb
----------------------------------------------------------------------------

Crea el to-do de bienvenida de cada usuario renderizando la plantilla
``project_todo.todo_user_onboarding``. Tres bloqueadores, los tres medidos:

1. **El compilador de QWeb no está portado, y lo dice él mismo.**
   ``IrQweb.render`` (``src/addons/base/models/ir_qweb.py:261``) levanta
   ``NotImplementedError`` a propósito: *"este árbol renderiza en el cliente
   (React) y no compila plantillas almacenadas"*. Sin ``_render`` no hay
   cuerpo del to-do, y la referencia hace ``continue`` cuando el cuerpo sale
   vacío — es decir, el porte fiel sería un no-op garantizado.
2. **La plantilla no existe.** ``data/todo_template.xml`` de la referencia
   es XML de datos del editor web (checklists, imágenes embebidas); este
   árbol no porta esa capa (criterio ya establecido: ``project_account``,
   ``account_debit_note``).
3. **``ResUsers.lang`` no existe.** La referencia hace
   ``self.with_context(lang=user.lang or self.env.user.lang)`` para renderizar
   en el idioma del usuario; medido, ``grep -n "lang"
   src/addons/base/models/res_users.py`` → **0 hits**.

Bloqueador de cuarto orden, para cuando se retome: la referencia crea la
tarea con ``user_ids: user.ids`` (M2M de asignados) y ``ProjectTask`` de este
árbol declara ``assignee``, FK simple (``addons/project/models/project_task.py:58``).

**Sucesor:** tarea PENDIENTE DE ASIGNAR — se retoma cuando exista un motor de
plantillas del lado servidor, o cuando el cuerpo de bienvenida se decida como
contenido del cliente React (que es donde este árbol lo pondría).

Corolario — el ``post_init_hook`` del addon también cae
=========================================================

El ``__init__.py`` de la referencia declara ``_todo_post_init``
(``odoo19c: addons/project_todo/__init__.py:5-6``), que siembra el to-do de
bienvenida a todos los usuarios internos existentes
(``search([("share", "=", False)])._generate_onboarding_todo()``). Cae con
``_generate_onboarding_todo``, y además ``share`` aquí es una ``property``
calculada (``src/addons/base/models/res_users.py:645``), no una columna: no
se puede filtrar con ella en el ORM. Ver el ``__init__.py`` de este addon.
"""
