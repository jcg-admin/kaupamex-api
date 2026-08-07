"""``ir.model`` extendido por ``web`` — API del selector de modelo dinámico.

Adaptación de ``odoo19c: addons/web/models/ir_model.py``
(``odoo-tools@622ddc2a``, 99 líneas, LGPL-3). Cinco métodos de una clase
(``IrModel``): ``display_name_for``/``_display_name_for``
(nombres visibles de una lista de modelos, filtrados por acceso),
``_is_valid_for_model_selector`` (el filtro de acceso que usan los dos
anteriores), ``get_available_models`` (todos los modelos accesibles al
usuario actual) y ``_get_definitions`` (metadatos de campo por modelo, para
el cliente).

**No se porta el contenido — 0 de 5 —** por dos razones medidas y distintas,
cada una ya aceptada en este mismo árbol para el mismo patrón de divergencia
(``models.py`` — familias ``search_panel``/``onchange`` — y
``bus/models/ir_model.py``).

1. **``display_name_for``/``_display_name_for``/``_is_valid_for_model_selector``/
   ``get_available_models`` sirven un único consumidor: el selector de
   modelo del campo ``Properties``.** Medido en la referencia
   (``grep -rln "display_name_for\\|get_available_models"
   addons/*/static/src`` → sólo ``web`` y ``spreadsheet``; dentro de
   ``web``, únicamente ``core/model_selector/model_selector.js`` y
   ``views/fields/properties/property_definition.js``): es el widget que
   deja elegir, en tiempo de ejecución, a qué modelo apunta un campo
   ``Properties`` dinámico. Este árbol porta ``Properties``/
   ``PropertiesDefinition`` como alias directo de ``JSONField``
   (``orm/fields_properties.py``) **sin** la semántica de
   ``definition_record``/selector de comodelo en tiempo de ejecución —
   verificado: los dos consumidores reales de ``Properties`` en este árbol
   (``fleet/models/fleet_vehicle{,_model}.py``) lo usan como JSON llano, sin
   picker de modelo. Mismo corte que DEC-03 (``ui-adaptacion-nativa``): este
   proyecto usa componentes React explícitos, no arch XML dinámico. Sin ese
   widget ni esa semántica, no hay quien llame a estos cuatro métodos.

2. **``_get_definitions`` es la misma familia que ``bus/models/ir_model.py``
   ya declaró ausente, con la misma razón.** El contrato de campos por
   modelo que este endpoint expone dinámicamente ya lo publica este árbol de
   forma estática vía OpenAPI (``drf-spectacular``, ``@extend_schema`` en
   354 puntos — skill ``backend-drf-spectacular``). Duplicarlo aquí
   produciría dos descripciones del mismo contrato divergiendo con el
   tiempo. Su único llamador en la referencia
   (``controllers/model.py::get_model_definitions``, ruta
   ``POST /web/model/get_definitions``) no tiene contraparte JS detectable
   (``grep -rln "get_definitions" addons/web/static/src`` → 0 hits): ni
   siquiera el propio cliente web la consume activamente hoy.

Nótese que ``ir.model`` **sí** está portado, y completo, en
``addons/base/models/ir_model.py``: lo que no se porta es esta **extensión**
del addon ``web``, no el modelo — mismo patrón que la nota de cierre de
``bus/models/ir_model.py``.
"""
