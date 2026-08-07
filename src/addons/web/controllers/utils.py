"""Utilidades HTTP compartidas del cliente web — adaptación de
``odoo19c: addons/web/controllers/utils.py``, licencia LGPL-3.

Completado 2026-08-07 contra H-API-369 / DEC-FW-04 — módulo de utilidades sin
ruta propia (la referencia tampoco expone rutas aquí), consumido por los
demás controladores de ``web``.

Medición símbolo-por-símbolo (``re.findall(r'^def (\\w+)', ref, re.M)`` — no
``^\\s{4}def``: la referencia no declara ninguna clase, sus símbolos son
funciones de módulo a columna 0 — mismo criterio de conteo que
``porte-completo-no-parcial.md``, adaptado a la forma real del archivo):
**8** funciones. **1 portada** (``is_user_internal``), **7 declaradas
ausentes** con razón — no hay recorte silencioso.

Por qué 7 de 8 son ausentes — consolidación, no descubrimiento nuevo
========================================================================

Cada uno de los siete ya tiene su ausencia declarada, con su causa raíz, en
un archivo hermano de este mismo addon (``home.py``, ``json.py``,
``session.py``) o en el módulo de acciones de ``base`` — este archivo no
abre casos nuevos, cruza los que ya estaban resueltos hacia el punto donde
la referencia los agrupa.

- **``get_action`` / ``get_action_triples``.** Declaradas AUSENTE en
  ``json.py`` (docstring, sección "Símbolos NO portados", punto 1 del
  cuerpo de ``WebJsonController.web_json_1``): no existe un índice de
  "nombre en URL → acción" en este proyecto; las rutas DRF se registran
  explícitas en cada ``urls.py``, no se resuelven por slug en runtime.
- **``ensure_db``.** Declarada AUSENTE en ``session.py`` (divergencia 1:
  "Sin parámetro ``db``... la base es una y la fija el despliegue; aceptarlo
  sería superficie sin función"). ``config/settings/base.py:266`` fija
  ``DATABASES['default']['NAME']`` desde ``DB_NAME`` de entorno al arrancar
  el proceso — no por request — y las bases ``company_<N>_db`` del modelo
  DB-per-company (``database.py``, este mismo addon) se administran vía la
  capacidad ``platform.provision``, no vía un parámetro ``?db=`` de sesión
  como en la referencia.
- **``_get_login_redirect_url``.** Declarada AUSENTE en ``home.py``
  (quinto punto de "Los 8 ausentes", bajo ``_login_redirect``): el
  primitivo del que depende SÍ está portado —``ResUsers.is_internal()``
  (``base/models/res_users.py:430``)— pero la orquestación de a dónde
  redirigir tras el login es trabajo del router de React (que ya recibe
  ``is_system``/``login``/``name`` de ``session_info()``), no de esta API.
- **``generate_views``.** El caso de acción **persistida** ya está cubierto,
  con forma distinta —propiedad computada, no función que muta un dict—:
  ``IrActionsActWindow.views`` (``base/models/ir_actions.py:284-307``,
  docstring "≙ ``_compute_views``"). El caso que ``generate_views`` resuelve
  en la referencia —generar ``views`` para un **dict de acción construido al
  vuelo** por un botón o una acción de servidor, sin registro en
  ``ir.actions.act_window``— no tiene consumidor aquí: las vistas DRF
  devuelven ``Response`` tipadas directamente en vez de un dict de acción
  para un gestor de acciones del lado cliente, y el único productor de esos
  dicts al vuelo en la referencia —``ir.actions.server.run()``— ya está
  declarado NO implementado por razón de seguridad (``json.py``, sección
  "Símbolos NO portados", punto de ``_get_action``: "montar un evaluador
  sobre entrada almacenada es superficie de ejecución de código").
- **``clean_action``.** Depende de ``env[action['type']]._get_readable_fields()``,
  la allowlist de campos por tipo de acción que un endpoint genérico de
  acciones filtraría antes de responder. Ese endpoint no existe en este
  proyecto: el único intento de resolución de acciones del addon
  (``json.py``) declara toda su cadena AUSENTE por falta del índice
  URL→acción de arriba, y ``_get_readable_fields`` en sí ya está declarado
  cubierto por el ``Meta.fields`` explícito de los serializers DRF, no por
  un método de modelo (``ir_embedded_actions.py`` e
  ``ir_actions_report.py``, ambos: "aquí eso lo declara el serializer DRF").
  Sin endpoint que lo llame y sin el primitivo que filtra, portar
  ``clean_action`` sería construir un filtro de dict genérico sin
  consumidor — el mismo riesgo de arquitectura sin consumidor que
  ``auto-audit-before-writing.md`` señala y que ``json.py`` ya invocó con
  este mismo criterio para no portar ``_get_action``.
- **``_local_web_translations``.** Depende de ``babel.messages.pofile`` para
  parsear archivos ``.po`` del bundle de traducciones JS de Odoo. Ni el
  paquete ni el árbol ``.po`` existen en este proyecto: ``babel`` no es
  dependencia declarada (``grep -in babel pyproject.toml`` → vacío;
  ``python3 -c "import babel"`` → ``ModuleNotFoundError``) y no hay ningún
  ``.po`` fuera de la propia referencia (``find … -iname "*.po"`` → 0
  resultados). El i18n de este backend pasa por
  ``django.utils.translation`` (``tools/translate.py``, ``_ = gettext_lazy``);
  el del frontend, por el mecanismo propio de ``kaupamex-ui``. Ninguno de
  los dos produce ni consume ``.po``.

Portado (1) — wrapper del primitivo ya existente
====================================================

``is_user_internal`` reduce a una búsqueda por ``pk`` seguida de una llamada
al primitivo que ``home.py`` ya cita como portado. No hay divergencia de
mecanismo que declarar: mismo contrato (recibe el id, no el registro),
mismo resultado.

Correspondencia con la referencia (``odoo-tools@622ddc2a``)
===============================================================

======================================  ======================================
Referencia                               Aquí
======================================  ======================================
``clean_action``                         AUSENTE — sin endpoint de acciones
                                          que lo consuma (``json.py``)
``ensure_db``                            AUSENTE — ≙ ``session.py``
                                          divergencia 1 (DB fija por
                                          despliegue)
``generate_views``                       AUSENTE — caso persistido cubierto
                                          por ``IrActionsActWindow.views``;
                                          caso de dict al vuelo sin
                                          consumidor
``get_action``                           AUSENTE — ≙ ``json.py``
``get_action_triples``                   AUSENTE — ≙ ``json.py``
``_get_login_redirect_url``              AUSENTE — ≙ ``home.py``
                                          (``_login_redirect``)
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
