"""Utilidades HTTP compartidas del cliente web — adaptación de
``odoo19c: addons/web/controllers/utils.py``, licencia LGPL-3
(``odoo-tools: addons/web/__manifest__.py``, DEC-KX-03).

Módulo de utilidades sin ruta propia (la referencia tampoco expone rutas
aquí), consumido por los demás controladores de ``web``.

Medición símbolo-por-símbolo (``re.findall(r'^def (\\w+)', ref, re.M)`` — no
``^\\s{4}def``: la referencia no declara ninguna clase, sus símbolos son
funciones de módulo a columna 0 — mismo criterio de conteo que
``porte-completo-no-parcial.md``, adaptado a la forma real del archivo):
**8** funciones. **1 portada** (``is_user_internal``), **7 declaradas
ausentes** con razón — no hay recorte silencioso.

Re-verificación 2026-08-07 (H-API-378/379) — la ausencia se re-midió, no se
heredó del docstring anterior
================================================================================

``porte-completo-no-parcial.md`` prohíbe tratar una ausencia ya declarada
como decisión cerrada: cada uno de los siete se volvió a medir hoy contra el
código actual (no contra la prosa de ``home.py``/``json.py``/``session.py``),
con comandos ejecutados en este pase. Dos hallazgos cambian la calidad de la
evidencia sin cambiar el veredicto:

1. **``ensure_db`` tiene un equivalente real, no una ausencia por diseño.**
   La medición anterior decía "aceptarlo sería superficie sin función", sin
   citar el mecanismo que lo reemplaza. Hoy existe y está wireado:
   ``CompanyContextMiddleware`` (``base/models/ir_http.py:216-253``) resuelve
   usuario→compañía por request y puebla ``orm.environments`` (el
   ``ContextVar`` que hace de ``env.company``); ``CompanyDatabaseRouter``
   (``orm/routers.py``) resuelve compañía→alias de base
   (``company_<N>_db``) para el router DB-per-company (SOL-091). Es
   exactamente el trabajo que ``ensure_db`` hace en la referencia —resolver
   qué base sirve esta petición— pero resuelto por middleware + router de
   Django, no por un parámetro ``?db=`` de sesión: no hay "selector de base"
   al que redirigir porque la resolución ya ocurrió antes de llegar a la
   vista. ``grep -rn "session\\[.company\\|active_company\\|CompanyMiddleware"
   src/`` fuera de ``orm/`` y ``base/models/ir_http.py`` → 0 — no hay un
   segundo mecanismo de selección de base que ``ensure_db`` pudiera cubrir.
2. **``get_action``/``get_action_triples``/``clean_action`` — el dato para
   resolverlos existe (``IrActionsActWindow.path``,
   ``base/models/ir_actions.py:145-192``, con los mismos tres chequeos de
   ``m-``/``action-``/nombre punteado que ``get_action`` valida), pero
   **ningún controlador lo consulta**: ``find src/addons/*/controllers -iname
   "*.py"`` no tiene un endpoint de resolución de acciones por URL, y
   ``base/controllers/`` sólo contiene ``schema.py``. Construir el resolutor
   sin el endpoint que lo llame sería exactamente la "arquitectura
   especulativa sin consumidor" que ``auto-audit-before-writing.md``
   prohíbe — el dato modelado no cambia esa conclusión, la aplaza a cuando
   exista el endpoint.

Los cinco restantes se re-confirmaron sin cambios de fondo (ver detalle por
símbolo abajo); las citas de código se re-verificaron contra HEAD de hoy, no
se copiaron del docstring previo.

Por qué 7 de 8 son ausentes — con la re-verificación de hoy
========================================================================

- **``get_action`` / ``get_action_triples``.** Sin índice URL→acción
  consumido por ningún controlador (medición 2 arriba). Declaradas también
  AUSENTE en ``json.py`` (``WebJsonController.web_json_1``, punto 1) por la
  misma causa raíz — las rutas DRF se registran explícitas en cada
  ``urls.py``, no se resuelven por slug en runtime.
- **``ensure_db``.** Cubierto por ``CompanyContextMiddleware`` +
  ``CompanyDatabaseRouter`` (medición 1 arriba) — no ausente "por diseño
  minimalista", ausente porque el problema que resuelve ya lo resuelve otra
  pieza, con otra forma (middleware de Django, no parámetro de sesión).
- **``_get_login_redirect_url``.** El primitivo del que depende SÍ está
  portado —``ResUsers.is_internal()`` (``base/models/res_users.py:430``)—
  pero la orquestación de a dónde redirigir tras el login es trabajo del
  router de React (que ya recibe ``is_system``/``login``/``name`` de
  ``session_info()``, ``session.py::_session_info``), no de esta API REST:
  ``session_authenticate`` devuelve un cuerpo JSON, no un ``302``. Re-medido
  hoy: ``session.py`` (re-leído completo) declara la brecha del segundo
  factor —``authz_totp`` existe pero "sólo expone gestión... no un corte en
  el login"— como trabajo propio pendiente, no como algo que este wrapper
  pudiera cerrar; construir el redirect sin el corte de login que lo
  motivaría sería la misma arquitectura sin consumidor.
- **``generate_views``.** El caso de acción **persistida** ya está cubierto,
  con forma distinta —propiedad computada, no función que muta un dict—:
  ``IrActionsActWindow.views`` (``base/models/ir_actions.py:284-307``,
  docstring "≙ ``_compute_views``"). El caso que ``generate_views`` resuelve
  en la referencia —generar ``views`` para un **dict de acción construido al
  vuelo** por un botón o una acción de servidor, sin registro en
  ``ir.actions.act_window``— no tiene consumidor aquí:
  ``grep -rln "view_mode" src/addons/*/views.py src/addons/*/controllers/*.py``
  → sólo este mismo archivo y ``json.py`` (ambos documentando la ausencia,
  ningún productor real de esa forma de dict). El único productor de esos
  dicts al vuelo en la referencia —``ir.actions.server.run()``— sigue NO
  implementado por razón de seguridad (``ir_actions.py``: "montar un
  evaluador sobre entrada almacenada es superficie de ejecución de código").
- **``clean_action``.** Depende de ``env[action['type']]._get_readable_fields()``,
  la allowlist de campos por tipo de acción que un endpoint genérico de
  acciones filtraría antes de responder. Sin endpoint (medición 2 arriba) y
  sin el primitivo que filtra —``_get_readable_fields`` sigue cubierto por
  ``Meta.fields`` explícito de los serializers DRF, no por un método de
  modelo (``ir_embedded_actions.py`` e ``ir_actions_report.py``, ambos
  re-leídos hoy: "aquí eso lo declara el serializer DRF")—, portar
  ``clean_action`` sería construir un filtro de dict genérico sin
  consumidor.
- **``_local_web_translations``.** Depende de ``babel.messages.pofile`` para
  parsear archivos ``.po`` del bundle de traducciones JS de Odoo. Re-medido
  hoy: ``babel`` no es dependencia declarada (``grep -in babel pyproject.toml
  uv.lock`` → vacío; ``python3 -c "import babel"`` →
  ``ModuleNotFoundError``) y **0** archivos ``.po`` fuera de ``.venv/`` y de
  ``odoo-tools`` (``find /home/user/kaupamex-api -iname "*.po" | grep -v
  odoo-tools | grep -v .venv | wc -l`` → 0 — los 1265 encontrados sin excluir
  ``.venv`` son locale de dependencias de terceros, ``rest_framework_
  simplejwt`` entre ellas, no del proyecto). El i18n de este backend pasa por
  ``django.utils.translation`` (``tools/translate.py``, ``_ = gettext_lazy``);
  el del frontend, por el mecanismo propio de ``kaupamex-ui`` — re-verificado
  hoy que **ningún** archivo de ``kaupamex-ui/src`` referencia
  ``/web/webclient/translations`` (``grep -rn`` → 0).

Portado (1) — wrapper del primitivo ya existente
====================================================

``is_user_internal`` reduce a una búsqueda por ``pk`` seguida de una llamada
al primitivo que ``home.py`` ya cita como portado. No hay divergencia de
mecanismo que declarar: mismo contrato (recibe el id, no el registro),
mismo resultado. Nota de estado (no cambia el porte, sólo lo declara):
``grep -rn "is_user_internal" src/ --include=*.py`` fuera de este archivo →
0 — su único llamador de la referencia (``_login_redirect``) sigue AUSENTE,
así que hoy tampoco tiene consumidor. Se mantiene portado porque el símbolo
en sí es correcto y barato; su falta de uso es la misma brecha de
``_get_login_redirect_url`` de arriba, no una nueva.

Correspondencia con la referencia (``odoo-tools@622ddc2a``)
===============================================================

======================================  ======================================
Referencia                               Aquí
======================================  ======================================
``clean_action``                         AUSENTE — sin endpoint de acciones
                                          que lo consuma
``ensure_db``                            AUSENTE — cubierto por
                                          ``CompanyContextMiddleware`` +
                                          ``CompanyDatabaseRouter``
``generate_views``                       AUSENTE — caso persistido cubierto
                                          por ``IrActionsActWindow.views``;
                                          caso de dict al vuelo sin
                                          consumidor
``get_action``                           AUSENTE — dato modelado
                                          (``IrActionsActWindow.path``), sin
                                          endpoint consumidor
``get_action_triples``                   AUSENTE — misma causa que
                                          ``get_action``
``_get_login_redirect_url``              AUSENTE — la API REST no redirige;
                                          la orquestación es del router React
``is_user_internal``                     ``is_user_internal()`` — nombre
                                          idéntico
``_local_web_translations``              AUSENTE — sin ``babel`` ni ``.po``
======================================  ======================================
"""
from addons.base.models import ResUsers


def is_user_internal(uid):
    """≙ referencia ``is_user_internal`` (``utils.py``, módulo).

    El primitivo real ya está portado: ``ResUsers.is_internal()``
    (``base/models/res_users.py:430``). Esta función es el wrapper de
    conveniencia que reemplaza ``request.env['res.users'].browse(uid)`` por
    una búsqueda directa por ``pk`` — mismo contrato de entrada (recibe el
    id, no el registro).

    :param uid: ``pk`` de ``ResUsers``.
    :returns: ``True`` si el usuario existe y pertenece a algún grupo
        ``user_type='internal'``; ``False`` en cualquier otro caso —
        incluido ``uid`` inexistente, que en la referencia equivale a
        iterar un recordset vacío (``any()`` sobre nada es ``False``).
    """
    user = ResUsers.objects.filter(pk=uid).first()
    return bool(user and user.is_internal())
