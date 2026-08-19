"""``base.import.module`` — addon ``base_import_module``.

BLOQUEADO EN SU TOTALIDAD — divergencia arquitectónica declarada, no
omisión silenciosa (``porte-completo-no-parcial.md``, desenlace (a)).

Qué hace la referencia
=========================================================================

Los ``31`` símbolos de ``odoo-tools@..., odoo19c:
addons/base_import_module/`` (``models/base_import_module.py``,
``models/ir_module.py`` — 755 líneas, el grueso —, ``models/ir_http.py``,
``models/ir_ui_view.py``, ``wizard/base_module_uninstall.py``,
``controllers/main.py``) implementan **instalar un módulo Odoo en
caliente**: subir un ``.zip``, extraerlo, parsear su ``__manifest__.py``,
crear la fila ``ir.module.module`` correspondiente, cargar sus XML/CSV/SQL
de datos vía ``ir.model.data`` (XMLID), registrar sus assets en
``ir.asset``, sus vistas en ``ir.ui.view``, sus estáticos y traducciones
como ``ir.attachment`` — y, en el módulo hermano ``ir_module.py``, además
consultar el App Store de Odoo (``https://apps.odoo.com``) para el catálogo
de industrias.

Por qué no hay pieza que portar (no "pieza ausente" — el CONCEPTO no aplica)
=========================================================================

Cada uno de esos siete mecanismos depende de que "instalar un módulo" sea
una operación en **runtime**, contra una base viva, disparada por un
usuario con un archivo. En este monolito Django, instalar un addon es
agregar un paquete Python a ``INSTALLED_APPS`` y correr sus migraciones —
una operación de **deploy**, en código versionado, nunca en runtime contra
producción. No es que falte una pieza (como ``ResourceCalendar.plan_days``
en ``base_automation``, donde el HUECO es puntual): es que el género de
operación —"cargar código nuevo mientras el proceso corre"— está fuera del
modelo de esta plataforma por diseño.

Esta plataforma YA tomó esta decisión, en el mismo lugar donde alguien
podría buscarla (precedente citado, no inventado en este pase):
``src/addons/base/models/ir_module.py`` — su propio docstring dice
verbatim: *"Las transiciones de Odoo (to install / to upgrade / to remove)
no se portan: son la máquina de estados de un instalador que aquí no
existe... Registrar un estado que nadie puede alcanzar sería inventar una
capacidad."* Ese ``IrModule`` SÍ existe (metadata técnica de los addons en
disco) — lo que no existe, ahí y aquí, es el INSTALADOR. ``base_import_
module`` es, completo, ese instalador: no tiene metadata propia que
agregar a ``IrModule``, sólo el motor de instalación en caliente que ya se
declaró fuera de alcance.

Mapa completo — los 7 archivos de la referencia y su símbolo
=========================================================================

- ``models/base_import_module.py`` (``BaseImportModule``, TransientModel —
  el wizard de subir el ``.zip``): ``import_module``,
  ``get_dependencies_to_install_names``, ``action_module_open``. Sin
  ``ir.module.module`` con instalador, no hay a qué apuntar el wizard.
- ``models/ir_module.py`` (``IrModuleModule``, ``_inherit`` — 27 métodos):
  parseo de manifest/zip, XMLID, assets, App Store, traducciones babel.
  Extiende un modelo — ``IrModule`` de este árbol — que **no** declara
  ``imported``/``module_type`` (ver arriba: esos campos describen un
  módulo instalado en caliente, que no puede existir).
- ``models/ir_http.py`` (``IrHttp._get_translations_for_webclient``):
  traducciones para el cliente web de Odoo (QWeb + JS). Sin cliente web,
  sin traducciones que servir por este canal.
- ``models/ir_ui_view.py`` (``IrUiView._validate_custom_views``): valida
  vistas QWeb importadas contra ``ir_model_data``/``ir_module_module``. Ni
  QWeb ni XMLID existen en este árbol.
- ``wizard/base_module_uninstall.py`` (``BaseModuleUninstall.
  _modules_to_display``): extiende el wizard de desinstalación de Odoo,
  que tampoco existe aquí (desinstalar = quitar de ``INSTALLED_APPS`` +
  revertir migraciones, en código, no un wizard en runtime).
- ``controllers/main.py`` (``ImportModule.login_upload``): endpoint HTTP
  ``auth='none'`` con login/password en el body — superado además por
  ``authz`` (JWT), que es como este árbol ya resuelve autenticación.

Este archivo es el único que se crea en el addon — documenta el veredicto
en el sitio donde el modelo principal de la referencia vivía. Los otros
seis sitios (``models/ir_module.py``, ``models/ir_http.py``, ``models/
ir_ui_view.py``, ``wizard/base_module_uninstall.py``,
``controllers/main.py``, y el ``models/__init__.py``/``wizard/__init__.py``
de soporte) se listan arriba en vez de crearse vacíos — un archivo Python
vacío no añade trazabilidad sobre lo que este docstring ya cubre completo,
y multiplicaría por seis el mismo veredicto sin nueva información.
"""
