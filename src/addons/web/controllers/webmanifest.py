"""Manifiesto PWA del cliente web — adaptación de
``odoo19c: addons/web/controllers/webmanifest.py``, licencia LGPL-3.

Completado 2026-08-07 contra H-API-369 / DEC-FW-04 — el addon ``web`` era una
cáscara de solo controladores (``session.py`` + ``export.py``, sin webmanifest).

Medición símbolo-por-símbolo (``re.findall(r'^\\s{4}def (\\w+)', ref)``, mismo
criterio que ``porte-completo-no-parcial.md``, sobre la clase única
``WebManifest``): **13** métodos. **2 portados** (adaptados, self-contenidos),
**11 declarados ausentes** con razón — no hay recorte silencioso.

Por qué 11 de 13 son ausentes — una sola causa raíz arquitectónica
====================================================================

La referencia sirve el **shell instalable** de un cliente web renderizado por
el propio backend: un manifiesto PWA con iconos propios, un service worker
JS, una página offline y una página de "app acortada" (*scoped app*), todos
resueltos por Odoo desde ``static/`` de sus addons y plantillas QWeb que
Odoo renderiza server-side bajo el scope ``/odoo``.

Este backend **no tiene ese shell, y no le corresponde tenerlo**. Medido:

- **0** directorios ``static/`` en los 78 addons de ``src/addons``
  (``find src/addons -maxdepth 2 -type d -iname static``) — no existe el
  mecanismo que la referencia usa para resolver ``file_open``/``file_path``
  de un icono o de un ``.js``.
- **0** renderizado de página completa por plantilla (los hits de ``render(``
  en ``src/addons`` son de email/reporte, no de un shell de cliente — no hay
  QWeb ni equivalente).
- El frontend (``kaupamex-ui``, React + Webpack) es una SPA **compilada
  aparte** y servida por Apache como estático (``server: config/apache/``),
  no embebida ni renderizada por Django. Verificado: ``ui/public/`` **no**
  tiene ``manifest.json`` ni service worker real (sólo ``mockServiceWorker.js``
  de MSW, herramienta de testing) y ``ui/public/index.html`` tiene **0**
  menciones de ``manifest``/``service-worker``/``theme-color``.

Un manifiesto PWA instalable es, por diseño, responsabilidad de quien sirve
el shell — aquí la SPA de ``ui/`` (patrón estándar: ``public/manifest.json``
+ ``<link rel="manifest">`` + registro de un service worker propio via
Webpack/Workbox), nunca la API REST detrás de ``/api/v2/``. Construirlo aquí
no sería completar una laguna del ORM (rule 7, ``porte-completo-no-parcial.md``)
sino levantar, sin un solo consumidor real en ningún lado del monorepo, una
capa que le pertenece a otro repo — la misma forma que ``search_panel`` y
``onchange`` en ``models.py`` de este addon: "componentes React explícitos,
no hay consumidor" (DEC-03 de ``ui-adaptacion-nativa``).

**Los 11 ausentes, agrupados por qué bloquea cada uno:**

- ``_get_shortcuts`` — resuelve, por addon instalado, el ``ir.ui.menu`` raíz
  vía ``ir.model.data`` (mapea *módulo → id de registro XML*). Este árbol no
  tiene ese registro: el ``key`` de ``base.IrUiMenu`` (que cumple el papel de
  xmlid, ver su propio módulo) está sembrado por **sección de dominio**
  (``sec-catalogo``, ``sec-ventas``…, ``authz: management/commands/seed_menu.py``),
  no por nombre de addon instalado — no hay ``mail``/``crm``/``project`` como
  claves de menú que mapear 1:1.
- ``_get_webmanifest`` / ``webmanifest`` — arman y sirven el manifiesto;
  dependen de ``_get_shortcuts`` (ausente) y de iconos bajo
  ``web/static/img/`` (no existen — ver causa raíz). Adaptar el ``scope``
  (``/odoo`` → ``/``) es trivial; los iconos y los shortcuts no lo son.
- ``service_worker`` / ``_get_service_worker_content`` — leen
  ``web/static/src/service_worker.js`` con ``file_open``, mecanismo ausente.
  Aunque se pudiera incrustar el contenido inline, un service worker sirve un
  *scope* de origen: el de esta API (``/api/v2/``) no es el de la SPA que
  necesitaría cachear sus rutas — publicarlo aquí no cachearía la app.
- ``_icon_path`` — un literal a un PNG que no existe en este árbol.
- ``offline`` / ``scoped_app`` — renderizan plantillas QWeb
  (``web.webclient_offline`` / ``web.webclient_scoped_app``) que no tienen
  equivalente: no hay motor de plantillas de página completa en esta API.
- ``scoped_app_icon_png`` / ``_get_scoped_app_icons`` — dependen de
  ``_get_scoped_app_shortcuts``/iconos SVG bajo
  ``{addon}/static/description/icon.svg`` (mecanismo ausente) y de
  ``image_process`` (no existe; sería construible con Pillow — sí disponible,
  ver ``api: pyproject.toml``— pero no hay archivo fuente que procesar).
- ``scoped_app_manifest`` — orquesta ``_get_scoped_app_icons`` (ausente) +
  los dos métodos portados abajo; sin iconos no produce un manifiesto válido.

Portados (2) — self-contenidos, quedan como bloques de construcción
======================================================================

Ninguno de los dos depende de un símbolo ausente ni de ``static/``; se
portan porque, igual que ``_get_read_group_order``/``_add_groupby_values``
en ``models.py`` de este mismo addon, son utilidad genérica reutilizable por
quien retome el shell instalable completo (trabajo de ``ui/``, fuera de
alcance de esta API) — DEC-FW-04, "sin recorte silencioso".
"""
from addons.base.models import IrModule

__all__ = ['_get_scoped_app_name', '_get_scoped_app_shortcuts']


def _get_scoped_app_name(app_id):
    """≙ referencia ``_get_scoped_app_name`` (``webmanifest.py``).

    Divergencia declarada: la referencia lee ``modules.Manifest.for_addon``
    (metadata del ``__manifest__.py`` en disco). Aquí el catálogo técnico de
    addons es un modelo de datos — ``base.IrModule`` (adaptación de
    ``ir.module.module``) —, así que se consulta ahí en vez del filesystem.
    Mismo contrato: nombre legible si existe, o el identificador crudo.
    """
    module = IrModule.objects.filter(name=app_id).first()
    if module is not None and module.shortdesc:
        return module.shortdesc
    return app_id


def _get_scoped_app_shortcuts(app_id):
    """≙ referencia ``_get_scoped_app_shortcuts`` (``webmanifest.py:172-173``).

    En la fuente es, verbatim, un punto de extensión sin lógica propia —
    ``return []`` — pensado para que otro addon lo sobrescriba. Se porta
    idéntico: no hay divergencia que declarar porque no hay mecanismo que
    adaptar.
    """
    return []
