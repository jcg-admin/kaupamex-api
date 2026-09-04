"""``ir.model`` extendido por ``web`` — API del selector de modelo dinámico.

Adaptación de ``odoo19c: addons/web/models/ir_model.py``
(``odoo-tools@622ddc2a``, 99 líneas, LGPL-3 — atribución y aviso de licencia
preservados, DEC-KX-03). Cinco métodos de una clase (``IrModel``):
``display_name_for``/``_display_name_for`` (nombres visibles de una lista de
modelos, filtrados por acceso), ``_is_valid_for_model_selector`` (el filtro
de acceso que usan los dos anteriores), ``get_available_models`` (todos los
modelos accesibles al usuario actual) y ``_get_definitions`` (metadatos de
campo por modelo, para el cliente).

**Re-medición independiente 2026-08-07** (H-API-378 — el docstring de
entrada declaraba 0 de 5 sin escribir código; no se hereda esa conclusión
sin re-verificarla, ver ``porte-completo-no-parcial.md``). Resultado de hoy:
**4 de 5 portados**, adaptados a este vocabulario; **1 ausente**
(``_get_definitions``) con razón medida hoy.

Medición símbolo-por-símbolo (``re.findall(r'^\\s{4}def (\\w+)', ref)``):
**5** métodos de **1** clase. El nodo ``class IrModel`` en sí **no** es un
símbolo ausente — es artefacto del medidor (H-API-379): este árbol extiende
``ir.model`` con funciones de módulo instaladas como ``classmethod``
(``chain_method`` de ``orm/method_chain.py``, pasándole el descriptor
explícito), no redeclarando la clase.

Qué SÍ se pudo portar, y con qué (Nivel 0a/0c — comandos de hoy)
==================================================================

La razón original para no portar los cuatro primeros era doble: (a) el único
consumidor real (el selector de modelo del campo ``Properties`` dinámico) no
existe en este árbol (DEC-03, componentes React explícitos, sin arch XML), y
(b) el chequeo de acceso de la referencia (``self.env.user._is_internal()``
+ ``model.has_access('read')``) parecía no tener destino porque la
autorización efectiva es por capacidad a nivel de vista (DEC-11), no por ACL
genérica por-modelo.

(a) sigue siendo cierto — medido hoy:
``grep -rln "model_selector\\|modelSelector\\|ModelSelector" ui/src/`` → **0**;
``grep -rln "PropertiesField\\|Properties(" src/addons/`` → sólo ``fleet`` y
``product``, ambos con comodelo **fijo** (``fleet.vehicle`` →
``fleet.vehicle.model``), sin picker dinámico. Pero (b) **no** era correcto:
existe la pieza que hacía falta. **Actualizado tras la tarea #204**: ese
chequeo lo resuelve ahora ``IrModelAccess._get_access_groups`` —la expresión
de grupos de la fuente— preguntada con ``matches`` contra
``ResUsers._get_group_ids``. Antes se componía a mano con
``has_global_access`` más la clausura de ``ResGroups._closure``/``implied_ids``,
porque el álgebra no estaba portada; esa composición cubría dos de los tres
desenlaces de la fuente y así lo declaraba. ``self.env.user._is_internal()`` tiene destino
real y exacto: ``ResUsers._is_internal()`` (``base/models/res_users.py:430``),
que YA resuelve el eje interno/portal/público por ``user_type`` de grupo.

Qué NO se porta, con su medición de hoy
=========================================

**``_get_definitions``** — sigue sin destino, por una razón distinta a la de
(a)/(b): este árbol ya tiene un equivalente construido y en uso para la
misma introspección de campos, ``_fields_get()``
(``web/controllers/export.py:530-546``, Rule 7: "Django no expone un
equivalente genérico a ``Model.fields_get()``... se construye"). Duplicar
``_get_definitions`` aquí describiría el mismo contrato dos veces divergiendo
con el tiempo. Y su único llamador en la referencia
(``controllers/model.py::get_model_definitions``,
``POST /web/model/get_definitions``) no tiene contraparte JS ni siquiera en
la propia referencia — medido hoy: ``grep -rln "get_definitions"
ui/src/`` → **0**; el contrato de campos por endpoint ya lo publica este
árbol de forma estática vía OpenAPI: ``grep -rn "@extend_schema"
src/ --include=*.py | wc -l`` → **209** puntos (drf-spectacular, skill
``backend-drf-spectacular``). Portar ``_get_definitions`` produciría una
tercera fuente de verdad para lo que ``_fields_get`` y ``@extend_schema`` ya
resuelven.

Adaptación de firma — ``user`` explícito, no ``self.env.user``
================================================================

La referencia usa ``@api.model`` + ``self.env.user``: el "usuario actual"
viaja implícito en el ``env``. Este árbol no tiene ``env`` — las cuatro
funciones aceptan ``user`` explícito, mismo patrón que
``authz/permissions.py::has_capability(request.user, ...)``. Se instalan como
``classmethod`` sobre ``IrModel`` (equivalente de ``@api.model`` — no operan
sobre un registro concreto, igual que ``IrModel._reflect_models``, que ya es
``classmethod`` en ``base``).
"""
from addons.base.models.ir_model import IrModel, IrModelAccess
from orm.method_chain import chain_method


def _has_access(user, model_name, access_mode='read'):
    """¿``user`` tiene ``access_mode`` sobre ``model_name``?

    ≙ ``model.has_access(mode)`` de la referencia, y ahora por su **mismo
    mecanismo**: la expresión de grupos que concede el modo
    (``IrModelAccess._get_access_groups``) preguntada contra los grupos
    efectivos del usuario (``ResUsers._get_group_ids``, que ya es la clausura
    transitiva).

    Antes se componía a mano —ACL global, más la clausura de
    ``implied_ids``, más un ``exists()``— porque el álgebra de expresiones no
    estaba portada, y esta función lo declaraba: *"un modelo que sólo abre el
    modo vía esa álgebra no resuelve aquí"*. La tarea **#204** portó
    ``tools/set_expression.py`` y con él ``_get_access_groups``, así que la
    frontera desapareció: los tres casos —sin ACL, con ACL global, con ACL por
    grupo— los decide ahora ``matches`` sobre la misma expresión que usa
    ``base``, en vez de dos consultas que sólo cubrían dos de los tres.
    """
    groups = IrModelAccess._get_access_groups(model_name, access_mode)
    return groups.matches(user._get_group_ids())


def _is_valid_for_model_selector(cls, user, model_name):
    """≙ ``_is_valid_for_model_selector`` (``odoo19c:
    web/models/ir_model.py:36-45``).

    Las cuatro condiciones de la referencia, con destino real cada una:
    usuario interno (``ResUsers._is_internal()``), el modelo existe
    (``django_model``), no transitorio, no abstracto, y acceso de lectura
    (``_has_access``, arriba).
    """
    try:
        model_row = cls.objects.get(model=model_name)
    except cls.DoesNotExist:
        return False
    return (
        user is not None
        and user._is_internal()
        and model_row.django_model is not None
        and not model_row.transient
        and not model_row.abstract
        and _has_access(user, model_name, 'read')
    )


def _display_name_for(cls, model_names):
    """≙ ``_display_name_for`` (``odoo19c: web/models/ir_model.py:28-34``).

    Una sola consulta para todos los modelos accesibles, igual que la
    referencia (``search_read`` con la lista completa).
    """
    rows = cls.objects.filter(model__in=model_names).values('name', 'model')
    return [
        {'display_name': row['name'], 'model': row['model']}
        for row in rows
    ]


def display_name_for(cls, user, model_names):
    """≙ ``display_name_for`` (``odoo19c: web/models/ir_model.py:10-26``).

    Nombres visibles de ``model_names`` que ``user`` puede acceder; los no
    accesibles se devuelven con su propio nombre técnico como
    ``display_name`` — mismo resultado tanto si el modelo no existe como si
    el usuario no tiene acceso (la referencia lo documenta así verbatim).
    """
    accessible = []
    not_accessible = []
    for model_name in model_names:
        if _is_valid_for_model_selector(cls, user, model_name):
            accessible.append(model_name)
        else:
            not_accessible.append({'display_name': model_name, 'model': model_name})
    return _display_name_for(cls, accessible) + not_accessible


def get_available_models(cls, user):
    """≙ ``get_available_models`` (``odoo19c: web/models/ir_model.py:47-54``).

    Todos los modelos reflejados en ``ir.model`` que ``user`` puede acceder,
    con su nombre visible.
    """
    accessible = [
        row.model for row in cls.objects.all()
        if _is_valid_for_model_selector(cls, user, row.model)
    ]
    return _display_name_for(cls, accessible)


def apply_web_extensions():
    """Cuelga las cuatro extensiones de ``web`` sobre ``base.IrModel``.

    ``classmethod`` en vez de instancia — ≙ ``@api.model`` de la referencia
    (no operan sobre un registro concreto). Se invoca desde
    ``WebConfig.ready()`` (``web/apps.py::_EXTENSIONES``), mismo patrón que
    ``ir_http.py``/``res_partner.py``.

    Se pasa ``classmethod(...)`` explícito: las cuatro son altas nuevas (0
    previa en ``base``), así que es el llamador quien declara el descriptor.
    El rodeo local ``_install_classmethod`` que vivía aquí se retiró al
    arreglar ``chain_method`` para descriptores (:ref:`h-api-381`, #222).
    """
    for name, func in (
            ('display_name_for', display_name_for),
            ('_display_name_for', _display_name_for),
            ('_is_valid_for_model_selector', _is_valid_for_model_selector),
            ('get_available_models', get_available_models),
    ):
        chain_method(IrModel, name, classmethod(func))
