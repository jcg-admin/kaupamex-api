"""``base.module.install.request`` / ``base.module.install.review`` — el asistente.

Adaptación pendiente de ``odoo19c: addons/base_install_request/wizard/
base_module_install_request.py`` (LGPL-3, 87 líneas) y de ``__init__.py``
(``_auto_install_apps``) — atribución y aviso de licencia preservados
(DEC-KX-03).

Porte BLOQUEADO — 0 de 6 símbolos
==================================

Los seis del asistente y su arranque. **El séptimo símbolo del addon,
``action_open_install_request``, YA NO está aquí: se portó** en
``ir_module_module.py`` de este mismo paquete.

Qué cambió respecto de la versión anterior de este docstring
=============================================================

Decía *«bloqueado en su totalidad»* con tres causas, y **dos de las tres eran
falsas al medirlas**:

.. code-block:: text

   grep -rn "upstream_dependencies" --include=*.py src/ addons/
   → src/addons/base/models/ir_module.py:443   (EXISTE — el docstring decía "0 hits")

   grep -rn "group_system" --include=*.py src/ addons/ | wc -l
   → 45                                        (EXISTE — se declaraba ausente)

   grep -rn "class MailTemplate" --include=*.py src/ addons/ | wc -l
   → 1                                         (EXISTE — se declaraba no portado)

Sólo la tercera se sostiene, y el veredicto ancho tapaba un método —la acción
de arriba— que no dependía de ninguna de ellas. Por eso el bloqueo pasa de
«el addon entero» a **una arista por símbolo**, que es lo que
``scripts/check_bloqueo_declarado.py`` exige y lo que hace recorrible el grafo.

El bloqueo real, medido
========================

.. code-block:: text

   grep -rn "def button_immediate_install" --include=*.py src/ addons/ | wc -l
   → 0
   grep -rn "def button_install" --include=*.py src/ addons/ | wc -l
   → 0

Es el acto central: instalar un addon contra una base viva. En esta plataforma
instalar es una operación de **deploy** (``INSTALLED_APPS`` + migración), no una
fila que un asistente escriba en tiempo de ejecución — el veredicto lo declara
``src/addons/base/models/ir_module.py``, y el porte de los símbolos que le
faltan a ese archivo es la tarea **#452**.

Símbolo a símbolo
==================

- ``BaseModuleInstallReview.action_install_module`` (``:81-87``) —
  BLOQUEADO por ``ir.module.module.button_immediate_install`` — el método no
  existe en este árbol (medido arriba: 0 definiciones). Sucesor: tarea **#452**,
  que porta lo que le falta a ``src/addons/base/models/ir_module.py``.
- ``_auto_install_apps`` (``__init__.py:9-21``) —
  BLOQUEADO por ``ir.module.module.button_install`` — misma medición, 0
  definiciones. Sucesor: tarea **#452**.
- ``BaseModuleInstallReview._get_depending_apps`` (``:69-79``) —
  BLOQUEADO por ``base.module.install.review`` — el ``TransientModel`` que lo
  aloja no está declarado; su cuerpo sí es portable, porque
  ``upstream_dependencies`` existe (``src/addons/base/models/ir_module.py:443``).
  Sucesor: la sub-iniciativa ``portar-asistente-base-install-request``, cuya
  condición de cierre es declarar los dos ``TransientModel`` con su migración.
- ``BaseModuleInstallReview._compute_modules_description`` (``:61-67``) —
  BLOQUEADO por ``ir.qweb._render`` — la descripción se arma con una plantilla
  QWeb, y el motor de plantillas de este árbol
  (``src/addons/base/models/ir_qweb.py``) no expone ese punto para una
  plantilla de addon. Sucesor: la misma sub-iniciativa.
- ``BaseModuleInstallRequest._compute_user_ids`` (``:22-25``) —
  BLOQUEADO por ``base.module.install.request`` — ídem: el modelo que lo aloja
  no existe todavía. El dato que lee **sí** está (``group_system``, 45 hits).
  Sucesor: la misma sub-iniciativa.
- ``BaseModuleInstallRequest.action_send_request`` (``:27-44``) —
  BLOQUEADO por ``mail.template.send_mail`` — la clase ``MailTemplate`` existe
  pero no declara ``send_mail`` (medido: 0 definiciones); el mecanismo de aviso
  de esta plataforma es ``addons/mail/models/notification_service.py``. Sucesor:
  la misma sub-iniciativa.

Lo que este archivo no cierra
==============================

Los seis de arriba. Cuatro dependen de la sub-iniciativa
``portar-asistente-base-install-request`` (declarar los dos ``TransientModel``
con su migración, y decidir el sustituto de la plantilla QWeb y del envío de
correo); dos dependen de la tarea **#452**.
"""
