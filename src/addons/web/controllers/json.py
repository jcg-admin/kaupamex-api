"""JSON genérico del cliente web — adaptación de
``odoo19c: addons/web/controllers/json.py``.

``LGPL-3`` (``web/__manifest__.py``) — copia + adaptación con atribución.

Qué es la referencia
=====================

``WebJsonController`` resuelve una ruta ``/json/1/<subpath>`` a una **acción**
(``ir.actions.act_window``), su **vista** (arch XML declarado en
``ir.ui.view``) y de ahí el *field spec* + dominio + agrupamiento con los que
llama a ``web_read``/``web_search_read``/``web_read_group`` — es decir,
reconstruye del lado servidor lo mismo que el cliente web de Odoo pediría
para pintar la pantalla de esa acción.

Medición símbolo-por-símbolo (mismo criterio que
``porte-completo-no-parcial.md``: ``^\\s{4}def`` para métodos de clase, ``^def``
para funciones de módulo): **8 símbolos** — 4 funciones de módulo
(``get_view_id_and_type``, ``get_default_domain``, ``get_date_domain``,
``get_groupby``) y 4 métodos de ``WebJsonController`` (``web_json``,
``web_json_1``, ``_check_json_route_active``, ``_get_action``).

Re-verificación 2026-08-07T16:21:04Z (H-API-378/379) — la ausencia se volvió
a medir, no se heredó de este mismo docstring
================================================================================

``porte-completo-no-parcial.md`` prohíbe tratar una ausencia ya declarada en
el archivo como decisión cerrada — es exactamente el defecto que costó
3,7 M de tokens y 0 símbolos en dos corridas previas (H-API-378). Este pase
volvió a medir las cuatro ausencias contra el código de HOY, no contra esta
prosa, con dos resultados:

1. **``get_groupby`` deja de estar completamente ausente.** Su rama de
   parseo explícito (``groupby``/``fields`` como cadenas separadas por
   comas) no depende de arch-XML — sólo la rama de *fallback* que deriva el
   agrupamiento de la vista pivot/graph/kanban lo necesita. Se porta la
   primera, se declara ausente la segunda (ver "Portado parcialmente"
   abajo).
2. **La razón de ``web_json_1`` sobre ``web_read_group`` estaba
   desactualizada.** Este mismo docstring decía "``model.web_read_group(...)``
   — declarada ausente en ``web/models/models.py``"; hoy **ya no es cierto**:
   se cerró en ``web/models/models.py:1409`` (``api@364ae62``,
   ``2026-08-07T13:50:45+00:00``) **después** de que este archivo se
   completara por última vez (``api@fe5dc82``, ``2026-08-07T11:07:22+00:00``,
   dos horas y media antes). La corrección **no reabre** ``web_json_1``: lo
   que lo bloquea son los otros dos mecanismos (índice URL→acción y vista
   arch-XML, ver "Símbolos NO portados" abajo), que ``web_read_group`` no
   sustituye — se corrige la cita, no el veredicto.

Correspondencia con la referencia (``odoo-tools@622ddc2a``)
===========================================================

===============================  ================================================
Referencia                        Aquí
===============================  ================================================
``get_view_id_and_type``          ``get_view_id_and_type`` — idéntico nombre y
                                   contrato; sin arch-XML porque no lo necesita
                                   (opera sobre ``action.views``, ya portado en
                                   ``ir_actions.py``).
``get_default_domain``            ``get_default_domain`` — sólo la rama
                                   ``ir.filters``; la rama ``filters_from_context``
                                   (arch-XML) declarada ausente.
``get_date_domain``               ``get_date_domain`` — firma cambiada:
                                   ``date_field`` explícito en vez de ``view_tree``
                                   (ver "Divergencias declaradas").
``_check_json_route_active``      ``check_json_route_active`` — sólo la rama
                                   ``ir.config_parameter``; la rama del flag
                                   ``demo`` del módulo declarada ausente (no existe
                                   ese campo, ver abajo).
``get_groupby``                   ``get_groupby`` — PARCIAL: sólo la rama de
                                   parseo explícito (``groupby``/``fields``);
                                   el *fallback* de vista pivot/graph/kanban
                                   declarado ausente (arch-XML).
``WebJsonController.web_json``    AUSENTE.
``WebJsonController.web_json_1``  AUSENTE.
``WebJsonController._get_action`` AUSENTE.
===============================  ================================================

Divergencias declaradas (de los símbolos SÍ portados)
=======================================================

1. **Los dominios son ``Q`` de Django, no listas polacas.** Igual que
   ``AND``/``OR`` en ``web/models/models.py``: la referencia devuelve una lista
   ``[('campo', '>=', valor), ...]`` que otro paso combina con
   ``Domain.AND``; aquí ``get_date_domain``/``get_default_domain`` devuelven
   directamente el ``Q`` combinado — es la misma información, en el tipo que
   este ORM ya usa.
2. **``get_date_domain`` recibe ``date_field`` en vez de ``view_tree``.** La
   referencia lee ``view_tree.attrib.get('date_start')`` del arch XML de la
   vista calendario/gantt/cohort. Sin arch XML no hay de dónde leerlo; se
   sube a parámetro explícito. Mismo patrón de "forma cambiada, misma
   capacidad observable" que ``export.py`` aplicó a ``_fields_get()``.
3. **``get_default_domain`` cambia ``eval_context``/``context`` por
   ``user``.** La referencia sólo necesita el contexto de Odoo para dos
   cosas: sustituir ``uid`` en el dominio guardado (``re.sub(r'\\buid\\b', ...)``)
   y, en la rama arch-XML (ausente aquí), evaluar dominios de filtros de
   vista con ``safe_eval``. Sin esa segunda rama, un ``user`` explícito basta
   para lo primero.
4. **Sin fecha de dependencia nueva.** La referencia usa
   ``dateutil.relativedelta`` para "primer día del mes siguiente";
   ``python-dateutil`` no es dependencia declarada de este proyecto
   (``grep -n dateutil pyproject.toml uv.lock`` → vacío) y añadirla no es
   parte de esta pasada (consolidación). Se calcula con aritmética de
   ``datetime.date`` de la librería estándar — mismo resultado, sin
   dependencia nueva.
5. **``get_view_id_and_type`` usa ``None``, no ``False``, como "sin vista
   explícita".** Idiomatismo Python vs. el ``False`` de Odoo; ambos leen como
   "vacío" en su lenguaje de origen.
6. **``get_groupby`` pierde el parámetro ``view_tree``.** La referencia lo
   recibe siempre (incluso cuando ``groupby`` viene explícito, por firma) y
   sólo lo usa en la rama de *fallback*. Sin esa rama (ver "Portado
   parcialmente" abajo) el parámetro no tiene función — se retira en vez de
   aceptarlo y no leerlo nunca, que sería una firma mentirosa.

Portado parcialmente (1) — rama de parseo explícito, sin *fallback* de vista
================================================================================

**``get_groupby(groupby=None, fields=None)``.** La referencia tiene dos
rutas: si el cliente ya manda ``groupby``/``fields`` (cadenas separadas por
comas), los parte y regresa; si no, los **deriva** de la vista pivot/graph
(``view_tree.findall('./field')`` y sus atributos ``type``/``invisible``) o
del ``default_group_by`` de una vista kanban. Sólo la primera ruta no
depende de arch-XML — se porta tal cual (``groupby.split(',')`` /
``fields.split(',')``, idéntico a la referencia). La segunda sigue AUSENTE:
``ir.ui.view`` no interpreta arch-XML para pantallas de datos (``ir_ui_view.py``:
"se porta el registro y las reglas de herencia; no el combinador para
listar/pivotar") y no hay consumidor de esa forma en este árbol
(``grep -rn "findall.*'./field'\|default_group_by" src/addons`` → 0 fuera de
esta referencia). Es la misma partición que ``get_date_domain`` ya aplicó a
``view_tree.attrib.get('date_start')`` — la forma explícita se porta, la
forma derivada-de-vista se declara ausente con su causa.

Símbolos NO portados — con su razón
=====================================

**``WebJsonController.web_json`` / ``web_json_1``.** El cuerpo de
``web_json_1`` depende de dos mecanismos ausentes — uno de **arquitectura**
(sin consumidor en este árbol de rutas DRF explícitas) y uno de
**seguridad** (bloqueado a propósito, no por carencia del ORM):

1. **Arquitectura — resolución de ``subpath`` a acción.**
   ``get_action_triples``/``get_action`` (``odoo19c:
   addons/web/controllers/utils.py``) resuelven un índice "nombre en URL →
   acción" que este proyecto no tiene: las rutas DRF se registran explícitas
   en cada ``urls.py`` (verificado hoy — 0 rutas por slug dinámico en
   ``src/addons/*/urls.py``), no se resuelven en runtime. Sin acción
   resuelta no hay ``model``, ``view_id`` ni ``record_id`` de los que
   partir — bloquea el método completo, no sólo la rama de agrupamiento.
2. **Arquitectura — vista arch-XML para el *field spec*.**
   ``model.get_view(view_id, view_type)`` + ``model._get_fields_spec(view)``
   derivan qué campos leer del arch XML de la vista de pantalla; sin vista
   (mismo ausente que la rama 2 de ``get_groupby``), no hay spec que derivar
   para ``web_read``/``web_search_read``.
3. **Corrección de hoy — ``model.web_read_group(...)`` YA NO es la razón.**
   Este docstring citaba ``web_read_group`` como cuarto mecanismo ausente;
   se cerró hoy en ``web/models/models.py:1409`` (``api@364ae62``,
   posterior a la última vez que se completó este archivo — ver
   "Re-verificación" al inicio del módulo). El punto (1) y el punto (2)
   arriba siguen bloqueando ``web_json_1`` de forma independiente: aunque
   ``web_read_group`` esté disponible, no hay ``domain``/``groupby``/
   ``aggregates`` que pasarle sin la acción y la vista resueltas.

``web_json`` es sólo el wrapper de redirección hacia ``web_json_1``; portarlo
solo (una redirección a una ruta que no puede funcionar) no tiene valor
observable.

**``WebJsonController._get_action``.** Depende del mismo índice ausente del
punto 1 arriba (arquitectura) — y además, cuando la acción resuelta es un
``ir.actions.server``, llama a ``action.run()``, que es la parte
genuinamente de **seguridad**: ``ir_actions.py`` ya declara ese método NO
implementado a propósito: *"montar un evaluador sobre entrada almacenada es
superficie de ejecución de código"* (misma decisión que
``ir_rule.domain_force``). Aunque el índice URL→acción existiera, esta rama
seguiría bloqueada — no es una laguna del ORM que "se construye" (Rule 7):
es la misma superficie de ejecución de código que el proyecto ya decidió no
abrir en ningún punto de entrada.

Precedente en este mismo addon
================================

Esta exclusión no es un atajo nuevo: ``web/models/models.py`` (completado
2026-08-07 contra el mismo H-API-369/DEC-FW-04) ya declaró ausentes, con
idéntica razón, la familia ``read_group`` completa (11 métodos),
``search_panel`` (7 métodos) y ``onchange`` — los tres por depender de la
vista arch-XML o de un despachador sin consumidor. Este archivo es la capa
HTTP de exactamente esos mecanismos; la exclusión aquí es la misma decisión
propagada a su punto de entrada, no una nueva.
"""
import ast
import re
from datetime import date

from django.core.exceptions import ValidationError
from django.db.models import Q

from exceptions import MissingError
from osv.expression import TRUE_DOMAIN, to_q

from addons.base.models import IrFilters, SystemParameter


def get_view_id_and_type(action, view_type=None):
    """≙ referencia ``get_view_id_and_type`` (``json.py``, módulo).

    ``action`` es cualquier objeto con ``.views`` (lista de
    ``(view_id, modo)``, ver ``IrActionsActWindow.views`` en
    ``ir_actions.py``), ``.view_mode`` (cadena separada por comas) y ``.pk``.
    """
    view_modes = [mode for mode in (action.view_mode or '').split(',') if mode]
    if not view_type:
        view_type = view_modes[0] if view_modes else None

    for view_id, mode in action.views:
        if view_type == mode:
            return view_id, view_type

    if view_type not in view_modes:
        raise ValidationError(
            "Tipo de vista inválido '%s' para la acción id=%s" % (view_type, action.pk)
        )
    return None, view_type


def get_default_domain(model, action, user=None):
    """≙ referencia ``get_default_domain`` (``json.py``, módulo) — sólo la
    rama ``ir.filters``. La rama ``filters_from_context`` (arch-XML) no se
    porta (ver docstring del módulo).

    :param model: clase de modelo Django (``model._meta.label`` ≙
        ``IrFilters.model_id``, convención ``app_label.ModelName`` — ver
        ``export.py``, divergencia 1).
    :param action: la acción cuyo ``pk`` acota el filtro por defecto
        (≙ ``action._origin.id`` de la referencia).
    :param user: usuario cuyo filtro privado cuenta, además de los
        compartidos (``user=None`` de la fila). Reemplaza a ``eval_context``
        (ver divergencia 3 del docstring del módulo).
    """
    model_label = model._meta.label
    scope = Q(action_id=action.pk) | Q(action_id__isnull=True)
    if user is not None:
        scope &= Q(user=user) | Q(user__isnull=True)
    else:
        scope &= Q(user__isnull=True)

    ir_filter = (
        IrFilters._default_manager
        .filter(scope, model_id=model_label, is_default=True, active=True)
        .first()
    )
    if ir_filter is None:
        return TRUE_DOMAIN

    domain_str = ir_filter.domain
    if user is not None:
        domain_str = re.sub(r'\buid\b', str(user.pk), domain_str)
    return to_q(ast.literal_eval(domain_str))


def get_date_domain(start_date, end_date, date_field):
    """≙ referencia ``get_date_domain`` (``json.py``, módulo).

    ``date_field`` reemplaza a ``view_tree`` (ver divergencia 2 del docstring
    del módulo) — el nombre del campo de fecha por el que filtrar, en vez de
    leerlo del atributo ``date_start`` de la vista calendario/gantt/cohort.
    """
    if not date_field:
        raise ValidationError('No se pudo determinar el campo de fecha de la vista.')

    if not start_date or not end_date:
        start_date = date.today().replace(day=1)
        if start_date.month == 12:
            end_date = start_date.replace(year=start_date.year + 1, month=1)
        else:
            end_date = start_date.replace(month=start_date.month + 1)

    return Q(**{'%s__gte' % date_field: start_date}) & Q(**{'%s__lt' % date_field: end_date})


def get_groupby(groupby=None, fields=None):
    """≙ referencia ``get_groupby`` (``json.py``, módulo) — sólo la rama de
    parseo explícito. La rama de *fallback* que deriva el agrupamiento de la
    vista pivot/graph/kanban (``view_tree``) no se porta — ver "Portado
    parcialmente" en el docstring del módulo.

    :param groupby: cadena separada por comas, o ``None``.
    :param fields: cadena separada por comas (agregados), o ``None``.
    :returns: tupla ``(groupby, fields)`` — cada una ``list[str]`` cuando se
        recibió como cadena no vacía, o ``None`` cuando no se recibió.
    """
    if groupby:
        groupby = groupby.split(',')
    if fields:
        fields = fields.split(',')
    else:
        fields = None
    return groupby, fields


def check_json_route_active():
    """≙ referencia ``WebJsonController._check_json_route_active``.

    Sólo la rama ``ir.config_parameter`` (``web.json.enabled``). La rama
    ``request.env.ref('base.module_base').demo`` no se porta: no existe un
    campo ``demo`` en ``IrModule`` (``base/models/ir_module.py`` — verificado,
    los únicos campos son ``name``/``shortdesc``/``summary``/``category``/
    ``version``/``license``/``application``/``auto_install``/``state``); este
    proyecto no modela "instalado con datos de demostración" porque no hay
    instalador que sembre demo data (``INSTALLED_APPS`` es estático).
    """
    if not SystemParameter.get_param('web.json.enabled'):
        raise MissingError('La ruta /json está deshabilitada (web.json.enabled).')
