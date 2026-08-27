"""``base.module.install.request`` — addon ``base_install_request``.

BLOQUEADO EN SU TOTALIDAD — mismo veredicto que ``addons/base_import_
module/models/base_import_module.py``, mismo hallazgo raíz. Se detalla
aquí porque el hallazgo raíz es idéntico pero el mecanismo concreto que lo
hereda es distinto (no ZIP/manifest — un flujo de pedir-y-aprobar).

Los 7 símbolos de la referencia (``odoo-tools@..., odoo19c:
addons/base_install_request/`` — ``models/ir_module_module.py``:
``action_open_install_request``; ``wizard/base_module_install_request.py``:
``BaseModuleInstallRequest._compute_user_ids``/``.action_send_request``,
``BaseModuleInstallReview._compute_modules_description``/
``._get_depending_apps``/``.action_install_module``; ``__init__.py``:
``_auto_install_apps``) implementan: un usuario interno **pide** activar
un módulo no instalado; se notifica por correo a ``base.group_system``
(los administradores del sistema, vía plantilla ``mail.template`` + QWeb);
un administrador **revisa** las apps dependientes
(``upstream_dependencies``) y **aprueba con un clic**
(``button_immediate_install``).

Por qué es el MISMO bloqueo, no uno nuevo
=========================================================================

Las tres etapas —pedir, revisar, aprobar— son ceremonia alrededor de UN
acto central: instalar un módulo en caliente contra una base viva
(``button_immediate_install``). Ese acto es precisamente el que
``src/addons/base/models/ir_module.py`` declara fuera de alcance de esta
plataforma (cita verbatim en el docstring de
``addons/base_import_module/models/base_import_module.py``): instalar un
addon aquí es una operación de **deploy** (``INSTALLED_APPS`` + migración),
no una fila que un wizard pueda escribir en runtime. Sin el acto central,
pedir su aprobación es pedir aprobación para algo que no se puede otorgar
— construir el flujo de todos modos sería, en las palabras que ``ir_
module.py`` ya usa, *"inventar una capacidad"*.

Las tres piezas de infraestructura que el flujo necesita, y por qué
ninguna cierra el hueco
=========================================================================

- **``base.group_system``** (grupo de administradores a notificar): este
  árbol no tiene grupos Odoo — la autorización es por capacidad
  (``authz``), y no existe una capacidad "gestionar módulos" porque no
  existe la acción que gestionaría (mismo argumento circular que arriba).
- **``mail.template`` + ``ir.qweb`` + ``mail_template.send_mail``**
  (envío de la notificación): no portados — sin cliente web ni motor QWeb
  de plantillas de correo en este árbol; el mecanismo de notificación real
  de esta plataforma es ``addons/mail/models/notification_service.py``
  (funciones ``notify_*`` explícitas, sin plantilla declarativa), pero
  notificar sobre un evento que no puede ocurrir no aporta nada nuevo que
  portar.
- **``IrModule.upstream_dependencies``/``button_immediate_install``**: no
  existen en ``src/addons/base/models/ir_module.py`` (medido: 0 hits) —
  exactamente los métodos que ``ir_module.py`` declaró no portables.

Este archivo es el único que se crea en el addon (mismo criterio que
``base_import_module``: un archivo vacío por cada uno de los otros dos
sitios de la referencia —``models/ir_module_module.py``, ``wizard/
base_module_install_request.py``— no añade trazabilidad sobre lo que este
docstring ya cubre completo).
"""
